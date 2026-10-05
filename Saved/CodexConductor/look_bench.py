"""LOOK BENCH: a reversible, NON-SAVING A/B of "look depth" on ONE Passage bay
(default P04 bay 4), for Gary's 5 Oct note that the passages read flat.
Plan and evidence: Docs/Conductor/LOOK_DEPTH_PLAN_2026-10-05.md.

WHY THE POOL (redesign 5 Oct): the first live run failed on its first spawn inside
PIE - `unreal.GameplayStatics.begin_deferred_actor_spawn_from_class` does not exist
in UE 5.8 Python, and the spawn-API probe found NO Python route that spawns actors
into a running PIE world (only EditorLevelLibrary / EditorActorSubsystem
spawn_actor_from_class/_from_object, which target the editor world). Property edits
on existing PIE actors DO work (the base and shadows states ran and restored). So:

  PREPARE  editor world, PIE NOT running. Refuses unless the dirty census is clean
           and no ZZ_LOOKBENCH_* actor exists. Plans the whole temp-actor POOL every
           state can need (fog volumes, lights, floor + puddles, strobe, glint light
           + bulb, underpass proxies, arch-ring border proxies, spare ties), WRITES
           the labels and the census to look_bench_prepare.json (fsynced, re-read)
           BEFORE the first spawn, then spawns each one into the EDITOR world,
           labelled ZZ_LOOKBENCH_*, tagged ZZ_LOOKBENCH, hidden in game, component
           invisible, lights at 0 cd, fog at 0 extinction, collision off, Movable.
           It dirties the map: expected. The bench NEVER saves. Logs
           LOOK_BENCH_PREPARED and LOOK_BENCH_NEEDS_DONT_SAVE_RESTART.
  CAPTURE  in PIE (PIE duplicates the editor world, so the pool exists there).
           Finds the PIE copies by tag + label, refuses if any pool actor a state
           needs is missing or if any is already lit, and per state only MOVES,
           SHOWS, HIDES and SETS PROPERTIES on them. No spawn call exists on the
           PIE side. Rerun fixes (5 Oct, after the 050217 white frames; see
           LookBench/20261005-050217/state_luma.json): show strobes OFF for the run
           (recorded + restored); the clip-start camera pose is read first and the
           underpass / arch proxies are placed AHEAD of it; per state a base return
           (luma must come back to the first base's), then a luma settle gate
           (CaptureMachine) before every clip, a frustum check
           (LOOK_BENCH_IN_VIEW|state|n_visible) and a route check after it. Gate
           failures do not stop the run; they turn LOOK_BENCH_OK into LOOK_BENCH_FAILED.
  HOLD     in PIE: apply BENCH_TOGGLES, hold HOLD_SECONDS, restore + verify.
  RESTORE  in PIE: re-apply every original in this prepare's capture records
           (newest first, so the oldest originals win) and hide the whole pool.
           Then logs LOOK_BENCH_NEEDS_DONT_SAVE_RESTART: the editor-world pool and
           the dirty map are discarded by a Don't-Save editor restart (Gary, 5 Oct
           overnight authority). The bench never deletes + saves.
  CLEANUP  optional, editor world, PIE NOT running: deletes the tagged
           ZZ_LOOKBENCH_* editor actors WITHOUT saving; refuses (deleting nothing)
           if any dirty package is not one PREPARE itself dirtied. A Don't-Save
           restart is still needed afterwards (the map stays dirty).
  PROBE    in PIE, read-only: resolves the bay, lights, edge slots, glint, cvars.

Toggles (any subset, each applied from the recorded base):
  shadows    cast_shadows + cast_volumetric_shadow ON for the bay's KEY lights
  haze       Local Fog Volumes of VARIED density, volumetric scattering raised on
             the bay's lights, one back-light beam thrown toward the camera path
  rake       a raking side-light pair at the corridor edges
  floor      one dark glossy plane (walnut MID, roughness lowered), top +0.5 cm
  floor_wet  the floor plane wetter, plus puddle discs
  strobe     a ~1 Hz strobe low over the floor
  edge       the bay's Flat V3 "Edge" slot swapped to a pale raw-board MID.
             The 5 Oct probe found edge_slots=0 for P04 bay 4, so there this toggle
             changes NOTHING; every state logs edge_slots and edge_effective.
  glint      a practical at the mirror position of one wing face for the route
  underpass  box proxies of the UNDERPASS_RIG_KIT_PLAN Phase B mock bay
  arch_ring_border  box-segment proxies of pointed arch-rib BORDERS spanning L<->R
             above the bay, faces toward the camera, arch_count instances receding
             at arch_spacing_cm (Gary: test vertical borders in P04). The existing
             ceiling tops are NOT hidden by this toggle (base = current tops).

Rules carried from memory, enforced here:
  - originals are READ, WRITTEN (flushed, fsynced, re-read, compared) and the path
    logged BEFORE the first change, in every mode that changes anything;
  - the bench announces its temps (ZZ_LOOKBENCH_* count, where, until when);
  - no save call exists in this file (the harness scans for one);
  - no spawn call exists on the PIE side (the harness scans the PIE adapter and
    proves LookBench never calls adapter.spawn*);
  - Unreal objects live only inside closures; module globals hold plain data only;
  - captures use NO exposure override (show exposure), and success markers are
    printed only after asserted restore + census.
"""
from __future__ import annotations

import builtins
import datetime
import json
import math
import os
import pathlib
import re
import struct
import time
import traceback
import zlib

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
BENCH_DIR = BASE / "LookBench"
PREPARE_RECORD_NAME = "look_bench_prepare.json"
CAPTURE_RECORD_NAME = "look_bench_originals.json"
SPAWN_PREFIX = "ZZ_LOOKBENCH_"
POOL_TAG = "ZZ_LOOKBENCH"
HANDLE_NAME = "PUSS_LOOK_BENCH_HANDLE"
STATE_NAME = "PUSS_LOOK_BENCH_STATE"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
TICKS_PER_SECOND = 24000          # Master tick rate as used by lighting_looks_p04_driver.py
ALL_TOGGLES = ("shadows", "haze", "rake", "floor", "floor_wet", "strobe", "edge", "glint", "underpass",
               "arch_ring_border")
LIGHT_FIELDS = ("cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity")
STREAM_CVAR = "r.Streaming.FullyLoadUsedTextures"
RESTART_MARKER = "LOOK_BENCH_NEEDS_DONT_SAVE_RESTART"

FLOOR_PARENT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
EDGE_PARENT = "/Engine/BasicShapes/BasicShapeMaterial"
CUBE = "/Engine/BasicShapes/Cube"
CYLINDER = "/Engine/BasicShapes/Cylinder"

DEFAULTS = {
    "passage": "P04",
    "bay": 4,
    "half_width_cm": 1450.0,        # P04 LOW_SIDE lamps stand at lane y +-1450 (PIE live_lights, 4 Oct)
    # Route direction. MEASURED 5 Oct (prepare 20261005-050217): in all 17 clips the PIE camera travelled +X at
    # y = 240000.0 exactly, while the neighbour-centroid frame for bay 4 came out yaw -25.35 deg (uneven lamp
    # counts per bay skew the centroids). None = the old neighbour-centroid direction.
    "route_yaw_deg": 0.0,
    "route_tol_deg": 10.0,           # clip camera travel vs frame fwd; more = LOOK_BENCH_ROUTE gate failure
    "shadow_keys_max": 4,
    # [inf] 5 Oct rerun values. Engine range is 0..2, default 1.0 (LocalFogVolumeComponent.h:20-25); the old
    # 0.10/0.25/0.55 were not the measured cause of the white frames (the P04 show strobe was), but haze is meant
    # to be subtle, so thinner and still varied near -> far.
    "haze_densities": (0.04, 0.10, 0.22),
    "haze_radius_cm": 700.0,
    "haze_height_falloff": 600.0,
    "haze_phase_g": 0.55,
    "haze_vsi": 1.0,                 # volumetric scattering on bay lights while hazed (was 2.5)
    # Bench light levels [inf]: rescaled toward the bay's own levels (P04 bay 4 LOW_SIDE 104/152, BEAM_L 440,
    # PRACTICAL_TUBE 1760; their intensity UNITS were not read - this version records them as light_meta.units).
    # The old values (beam 6000, rake 2500, strobe 12000, glint 1500, shaft 8000 cd) were 4-80x those levels.
    "beam_cd": 900.0,
    "rake_cd": 350.0,
    "rake_height_cm": 140.0,
    "rake_x_offset_cm": -80.0,       # toward the approaching camera from the bay centre
    "floor_scalars": {"Roughness_Low": 0.08, "Roughness_High": 0.22},
    "floor_wet_scalars": {"Roughness_Low": 0.02, "Roughness_High": 0.06, "Roughness_Add_Grunge": 0.6},
    "puddle_scalars": {"Roughness_Low": 0.0, "Roughness_High": 0.0},
    "puddles": ((-250.0, -400.0, 260.0), (120.0, 350.0, 340.0), (420.0, -120.0, 200.0),
                (-520.0, 600.0, 180.0), (650.0, 700.0, 240.0)),   # (dx, dy, diameter) in bay frame
    "strobe_hz": 1.0,
    "strobe_duty": 0.12,
    "strobe_cd": 3000.0,
    "edge_color": (0.62, 0.50, 0.36, 1.0),   # raw softwood / paper core
    "edge_max_components": 64,
    "lead_seconds": 4.0,
    "clip_seconds": 5.0,
    "clip_fps": 6.0,
    # Settle gate (CAPTURE). The show uses AUTO exposure and the bench never overrides it (memory: capture
    # exposure convention), so before every clip the bench waits until the PICTURE has stopped changing:
    # small HighResShot probes every probe_interval_s, mean Rec.709 luma (0-255 sRGB values, the same measure as
    # LookBench/<prepare>/state_luma.json); stable = the last settle_window probes within
    # max(settle_tol_abs, settle_tol_rel * mean). Not stable by settle_max_seconds = LOOK_BENCH_SETTLE_FAILED
    # (gate failure; the clip is still recorded, flagged). settle_min_seconds counts from the first scrub.
    "repose_seconds": 1.0,           # re-scrub after this (a jump's first frame is stale), probes start after it
    "settle_min_seconds": 4.0,
    "settle_max_seconds": 20.0,
    "settle_ticks": 45,
    "probe_interval_s": 0.5,
    "probe_timeout_s": 4.0,
    "probe_resolution": (256, 144),
    "settle_window": 4,
    "settle_tol_abs": 2.0,
    "settle_tol_rel": 0.03,
    # Between states: back to base, settle, and the settled base luma must come back to the first base's.
    "base_return": True,
    "base_return_tol_abs": 4.0,
    "base_return_tol_rel": 0.10,
    # Show strobes (AInfinityStageStrobeLight): "off" = strobe_enabled False for the whole CAPTURE (recorded,
    # restored). MEASURED 5 Oct: the P04 default strobe (placed 00:44, 20000 cd peak, ghost PPV exposure bias +0.4,
    # bloom 2.0) put a 1.0 s white sawtooth into EVERY bay-4 state, base included. "keep" leaves them running.
    "show_strobes": "off",
    "pose_seconds": 1.5,             # CAPTURE first reads the PIE camera pose at the clip start (anchor + frustum)
    "fov_fallback_deg": 90.0,        # [inf] used only if the camera manager returns no FOV
    "hold_seconds": 120.0,
    "resolution": (1280, 720),
    # glint: a practical placed at the MIRROR position of one wing face for the camera route
    "glint_mesh_contains": "ruined_gallery_R_v3",   # W&T wet-paper test flat, P04 Wing 008 R
    "camera_height_cm": 150.0,       # [inf] cat-eye height; clip frames record the real camera location
    "glint_cam_distances": (1000.0, 800.0, 1200.0, 600.0, 1500.0, 1800.0, 400.0, 2200.0),
    "glint_light_dist_cm": 700.0,
    "glint_z_range": (40.0, 1100.0),
    "glint_cd": 400.0,               # was 1500: bay 9 glint lifted whole-frame mean luma 26 -> 70 (measured 5 Oct)
    "glint_source_radius_cm": 2.0,   # small source = tight specular highlight
    # underpass: the Phase B mock bay of UNDERPASS_RIG_KIT_PLAN_2026-10-05.md section 4, as box
    # proxies (SM_UP_* are not imported yet)
    "underpass_column_outset_cm": 60.0,
    "underpass_deck_z_cm": 2000.0,
    "underpass_tie_every_cm": 45.0,
    "underpass_steel": (0.035, 0.045, 0.04, 1.0),
    "underpass_concrete": (0.18, 0.17, 0.16, 1.0),
    "underpass_shaft_cd": 1500.0,
    # Underpass and arches are placed AHEAD OF THE CAMERA (anchor "camera": along-route distance from the PIE
    # camera pose read at the clip start), not at the bay centre. MEASURED 5 Oct: the bay-4 clip camera starts
    # 120 cm before the bay centre and travels only ~290 cm, so a deck at 20 m straight overhead and arches at
    # dx 0/500/1000 on a -25 deg axis were outside the view. "bay" = the old bay-centre placement.
    "underpass_anchor": "camera",
    "underpass_ahead_cm": None,      # None = auto from the live pose: deck at underpass_deck_frame_frac of the
    "underpass_deck_frame_frac": 0.8,  # half frame height above centre (90 deg h-FOV 16:9 -> ~40 m ahead of camera)
    "anchor_ahead_clamp_cm": (1500.0, 8000.0),
    # arch_ring_border: pointed arch-rib borders. [inf] look-test values chosen so the band crosses the upper
    # part of the frame from the cat-eye camera; every state is frustum-checked live (LOOK_BENCH_IN_VIEW).
    "arch_anchor": "camera",
    "arch_first_ahead_cm": None,     # camera anchor: None = auto, the FIRST arch's apex at arch_apex_frame_frac
    "arch_apex_frame_frac": 1.2,     # of the half frame height above centre: >1 = the first arch's apex just out of
                                     # frame, its band crossing the upper third; the next two recede whole
    "arch_min_visible_frac": 0.25,   # gate: at least this share of arch segments inside the clip-start frustum
    "arch_count": 3,
    "arch_spacing_cm": 500.0,
    "arch_first_dx_cm": 0.0,         # bay anchor only
    "arch_half_span_cm": None,       # None = the corridor half width
    "arch_spring_z_cm": 250.0,       # was 550 (apex 2266, out of view); now apex ~1840
    "arch_radius_factor": 0.55,      # R = factor * span; > 0.5 gives a pointed (two-centred) arch (was 0.6)
    "arch_segments_per_side": 6,
    "arch_band_cm": 150.0,           # radial depth of the rib band
    "arch_thick_cm": 12.0,           # along the route
    "arch_overlap_cm": 4.0,          # chord overlap so the band reads continuous
    "arch_color": (0.06, 0.055, 0.05, 1.0),
    # PREPARE: spare underpass ties beyond the editor-world count (PIE pitch may differ slightly)
    "pool_tie_margin": 10,
    "prepare_bays": ({"bay": 4}, {"bay": 9, "glint_mesh_contains": "coventry_ruin_R_v1"}),
}


# --------------------------------------------------------------------------
# pure helpers (no Unreal): tested offline by test_look_bench.py
# --------------------------------------------------------------------------

def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def bay_prefixes(passage, bay):
    n = int(passage[1:])
    return ("P%02d Wing %03d " % (n, bay), "P%02d LOOK B%02d " % (n, bay))


def normalise_toggles(toggles):
    out = []
    for t in toggles:
        if t not in ALL_TOGGLES:
            raise ValueError("LOOK_BENCH_BAD_TOGGLE|" + str(t))
        if t not in out:
            out.append(t)
    if "floor_wet" in out and "floor" in out:
        out.remove("floor")          # wet is a floor variant, not a second plane
    return tuple(out)


def default_states(glint_available=True):
    states = [("base", ())]
    for t in ALL_TOGGLES:
        if t == "glint" and not glint_available:
            continue
        states.append((t, (t,)))
    if glint_available:
        states.append(("glint_wet", ("glint", "floor_wet")))
    states.append(("all", ("shadows", "haze", "rake", "floor_wet", "strobe", "edge", "underpass")
                   + (("glint",) if glint_available else ())))
    return states


def same_level(world_a, world_b):
    """Editor world path vs its PIE duplicate: PIE prefixes the map name with UEDPIE_<n>_."""
    strip = lambda w: re.sub(r"UEDPIE_\d+_", "", str(w or ""))
    return bool(world_a) and bool(world_b) and strip(world_a) == strip(world_b)


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mul(a, k):
    return tuple(x * k for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _unit(a):
    n = math.sqrt(_dot(a, a))
    if n < 1e-9:
        raise ValueError("zero vector")
    return _mul(a, 1.0 / n)


def rotator_axes(yaw, pitch, roll):
    """World X/Y/Z axes of a UE FRotator, transcribed from FRotationTranslationMatrix
    (UE_5.8 Engine/Source/Runtime/Core/Public/Math/RotationTranslationMatrix.h:72-84)."""
    sp, cp = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    sr, cr = math.sin(math.radians(roll)), math.cos(math.radians(roll))
    x = (cp * cy, cp * sy, sp)
    y = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    z = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
    return x, y, z


def glint_solution(face_point, face_normal, frame, p):
    """Place a light so its MIRROR reflection off the face reaches a camera on the
    route: L = P + d * reflect(v), with v = unit(C - P) and reflect(v) = 2(n.v)n - v.
    Cameras sit on the route line (bay-frame lateral 0) at camera_height_cm, at each
    candidate distance before the face; the first whose light lands in the height
    band and within the corridor + 6 m wins."""
    fwd3 = (frame["fwd"][0], frame["fwd"][1], 0.0)
    n = _unit(face_normal)
    if _dot(n, fwd3) > 0:                       # the face must look back at the approaching camera
        n = _mul(n, -1.0)
    ox, oy, _ = frame["origin"]
    along_face = (face_point[0] - ox) * fwd3[0] + (face_point[1] - oy) * fwd3[1]
    zlo, zhi = p["glint_z_range"]
    tried = []
    for dist in p["glint_cam_distances"]:
        s = along_face - dist
        cam = (ox + fwd3[0] * s, oy + fwd3[1] * s, float(p["camera_height_cm"]))
        v = _unit(_sub(cam, face_point))
        nv = _dot(n, v)
        if nv < 0.1:
            tried.append([dist, "grazing_or_behind"])
            continue
        r = _sub(_mul(n, 2.0 * nv), v)
        light = _add(face_point, _mul(r, float(p["glint_light_dist_cm"])))
        lat = -(light[0] - ox) * fwd3[1] + (light[1] - oy) * fwd3[0]
        if not (zlo <= light[2] <= zhi):
            tried.append([dist, "z %.0f" % light[2]])
            continue
        if abs(lat) > float(p["half_width_cm"]) + 600.0:
            tried.append([dist, "lateral %.0f" % lat])
            continue
        return {"light": light, "camera": cam, "camera_distance_cm": dist, "normal": n,
                "incidence_deg": math.degrees(math.acos(max(-1.0, min(1.0, nv)))), "tried": tried}
    return {"light": None, "tried": tried}


def centroid(points):
    if not points:
        return None
    n = float(len(points))
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def bay_frame(here, before, after, half_width, route_yaw=None):
    """Origin at the bay centroid on the floor, fwd along the route, right across it.
    route_yaw (deg) given: fwd is that direction and the pitch is the neighbours' spacing
    PROJECTED on it. None: fwd from the neighbours' centroids (skews when bays carry
    uneven lamp counts: P04 bay 4 came out -25.35 deg on a straight +X route, 5 Oct).
    Falls back to +X (P04 is straight)."""
    if here is None:
        raise RuntimeError("LOOK_BENCH_BAY_NOT_FOUND")
    a = before or here
    b = after or here
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    span = 2.0 if (before and after) else 1.0
    if route_yaw is not None:
        fwd = (math.cos(math.radians(route_yaw)), math.sin(math.radians(route_yaw)))
        pitch = abs(dx * fwd[0] + dy * fwd[1]) / span
    elif length < 1.0:
        fwd = (1.0, 0.0)
        pitch = 0.0
    else:
        fwd = (dx / length, dy / length)
        pitch = length / span
    return {"origin": (here[0], here[1], 0.0), "fwd": fwd, "right": (-fwd[1], fwd[0]),
            "yaw_deg": math.degrees(math.atan2(fwd[1], fwd[0])),
            "pitch_cm": pitch, "half_width_cm": float(half_width)}


def resolve_bay(adapter, passage, bay, half_width, route_yaw=None):
    """Bay lights -> (ids, light rows, frame). Shared by PREPARE (editor) and CAPTURE (PIE)."""
    ids = adapter.find_lights(bay_prefixes(passage, bay))
    if not ids:
        raise RuntimeError("LOOK_BENCH_NO_BAY_LIGHTS|%s bay %d" % (passage, bay))
    lights = {lid: adapter.read_light(lid) for lid in ids}
    here = centroid([lights[l]["location"] for l in ids])
    before = centroid([adapter.read_light(l)["location"]
                       for l in adapter.find_lights(bay_prefixes(passage, bay - 1))]) if bay > 1 else None
    after = centroid([adapter.read_light(l)["location"]
                      for l in adapter.find_lights(bay_prefixes(passage, bay + 1))])
    return ids, lights, bay_frame(here, before, after, half_width, route_yaw)


def to_world(frame, dx, dy, z):
    ox, oy, _ = frame["origin"]
    fx, fy = frame["fwd"]
    rx, ry = frame["right"]
    return (ox + fx * dx + rx * dy, oy + fy * dx + ry * dy, z)


def _box(label, centre, yaw, size_cm, color, roll=0.0):
    return {"label": label, "kind": "mesh", "mesh": CUBE, "loc": centre, "yaw": yaw, "roll": roll,
            "scale": tuple(v / 100.0 for v in size_cm),
            "material": {"mid_parent": EDGE_PARENT, "vectors": {"Color": tuple(color)}}}


def pointed_arch_profile(half_span, spring_z, radius, n):
    """Two-centred (pointed) arch in the bay's (lateral y, height z) plane. The left
    half is an arc of radius R centred at (R - s, spring_z), rising from the left
    springing (-s, spring_z) to the apex on y = 0; the right half mirrors it.
    Returns n+1 intrados points per side, springing -> apex."""
    s, r = float(half_span), float(radius)
    if r < s:
        raise ValueError("LOOK_BENCH_ARCH_RADIUS|R %.1f < half span %.1f (not an arch)" % (r, s))
    cy = r - s
    t_apex = math.acos(max(-1.0, min(1.0, cy / r)))
    left = [(cy - r * math.cos(t_apex * k / n), spring_z + r * math.sin(t_apex * k / n)) for k in range(n + 1)]
    left[-1] = (0.0, left[-1][1])
    right = [(-y, z) for y, z in left]
    return {"L": left, "R": right, "centres": {"L": (cy, spring_z), "R": (-cy, spring_z)},
            "apex_z": spring_z + r * math.sin(t_apex), "radius": r}


def anchor_dx(frame, p, anchor, key_anchor, key_ahead, key_bay):
    """Along-route dx (bay frame) for a proxy group: camera anchor = the clip-start camera's
    along-route position + key_ahead; otherwise (or with no anchor read yet) p[key_bay]."""
    if p.get(key_anchor) == "camera" and anchor is not None:
        ahead = p.get(key_ahead)
        if ahead is None:
            ahead = anchor["auto"][key_ahead]
        return float(anchor["along_cm"]) + float(ahead)
    return float(p[key_bay]) if key_bay else 0.0


def auto_ahead(p, cam_z, fov_deg, aspect):
    """Distances ahead of the camera at which a feature of height H appears at frac x the half
    frame height above centre, for a LEVEL camera: d = (H - cam_z) / (frac * tan(vfov / 2)).
    Arch: H = the apex of a pointed arch of the configured profile. Clamped."""
    tan_v = math.tan(math.radians(float(fov_deg)) / 2.0) / float(aspect)
    lo, hi = p["anchor_ahead_clamp_cm"]
    clamp = lambda d: max(float(lo), min(float(hi), d))
    hw = float(p.get("arch_half_span_cm") or p["half_width_cm"])
    apex = pointed_arch_profile(hw, float(p["arch_spring_z_cm"]), float(p["arch_radius_factor"]) * 2.0 * hw,
                                int(p["arch_segments_per_side"]))["apex_z"]
    return {"arch_first_ahead_cm": clamp((apex - cam_z) / (float(p["arch_apex_frame_frac"]) * tan_v)),
            "underpass_ahead_cm": clamp((float(p["underpass_deck_z_cm"]) - cam_z)
                                        / (float(p["underpass_deck_frame_frac"]) * tan_v))}


def camera_anchor(frame, cam_loc, p=None, fov_deg=None, aspect=None):
    """The camera's along-route / lateral position in the bay frame (+ auto distances when p given)."""
    ox, oy, _ = frame["origin"]
    dx, dy = cam_loc[0] - ox, cam_loc[1] - oy
    out = {"along_cm": dx * frame["fwd"][0] + dy * frame["fwd"][1],
           "lateral_cm": dx * frame["right"][0] + dy * frame["right"][1], "camera": list(cam_loc)}
    if p is not None:
        out["auto"] = auto_ahead(p, cam_loc[2], fov_deg or p["fov_fallback_deg"],
                                 aspect or float(p["resolution"][0]) / float(p["resolution"][1]))
    return out


def arch_specs(frame, p, anchor=None):
    """Box-segment proxies of arch_count pointed arch-rib borders, each a band whose
    INNER edge (intrados) follows the profile, thin along the route so its face
    looks at the approaching camera, receding at arch_spacing_cm."""
    hw = float(p.get("arch_half_span_cm") or frame["half_width_cm"])
    n = int(p["arch_segments_per_side"])
    band, thick, overlap = float(p["arch_band_cm"]), float(p["arch_thick_cm"]), float(p["arch_overlap_cm"])
    prof = pointed_arch_profile(hw, float(p["arch_spring_z_cm"]), float(p["arch_radius_factor"]) * 2.0 * hw, n)
    yaw = frame["yaw_deg"]
    specs = []
    for i in range(int(p["arch_count"])):
        dx = anchor_dx(frame, p, anchor, "arch_anchor", "arch_first_ahead_cm", "arch_first_dx_cm")             + i * float(p["arch_spacing_cm"])
        for side in ("L", "R"):
            pts, cen = prof[side], prof["centres"][side]
            for k in range(n):
                (y0, z0), (y1, z1) = pts[k], pts[k + 1]
                length = math.hypot(y1 - y0, z1 - z0)
                du, dz = (y1 - y0) / length, (z1 - z0) / length
                my, mz = (y0 + y1) / 2.0, (z0 + z1) / 2.0
                ny, nz = _unit((my - cen[0], mz - cen[1]))      # outward, perpendicular to the chord
                cy, cz = my + ny * band / 2.0, mz + nz * band / 2.0
                spec = _box(SPAWN_PREFIX + "ARCH_%d_%s%02d" % (i, side, k), to_world(frame, dx, cy, cz), yaw,
                            (thick, length + overlap, band), p["arch_color"],
                            roll=math.degrees(math.atan2(-dz, du)))
                spec["arch"] = {"index": i, "dx": dx, "side": side, "inner": [[y0, z0], [y1, z1]],
                                "chord_cm": length}
                specs.append(spec)
    return specs


def plan_spawns(frame, toggles, p, glint=None, anchor=None):
    """Plain pool specs (label, kind, transform, properties). Labels all start with
    SPAWN_PREFIX. PREPARE spawns one actor per label; CAPTURE places and shows them.
    anchor: camera_anchor() of the clip-start camera (positions only; labels never depend on it)."""
    specs = []
    yaw = frame["yaw_deg"]
    pitch_cm = max(frame["pitch_cm"], 600.0)
    hw = frame["half_width_cm"]
    if "haze" in toggles:
        dens = p["haze_densities"]
        for i, d in enumerate(dens):
            dx = (-0.5 + i / max(1, len(dens) - 1)) * pitch_cm   # near -> far
            specs.append({"label": SPAWN_PREFIX + "HAZE_%d" % i, "kind": "fog",
                          "loc": to_world(frame, dx, 0.0, 250.0), "yaw": yaw,
                          "radius_cm": p["haze_radius_cm"], "density": d,
                          "height_falloff": p["haze_height_falloff"], "phase_g": p["haze_phase_g"]})
        specs.append({"label": SPAWN_PREFIX + "BEAM_BACK", "kind": "spot",
                      "loc": to_world(frame, 0.9 * pitch_cm, 0.15 * hw, 1100.0),
                      "rot": {"yaw": yaw + 180.0, "pitch": -28.0}, "cd": p["beam_cd"],
                      "color": (0.75, 0.85, 1.0), "inner": 6.0, "outer": 14.0,
                      "radius": 3000.0, "shadows": False, "vsi": 4.0})
    if "rake" in toggles:
        for side, sign, color in (("L", -1.0, (1.0, 0.82, 0.62)), ("R", 1.0, (0.62, 0.75, 1.0))):
            specs.append({"label": SPAWN_PREFIX + "RAKE_" + side, "kind": "spot",
                          "loc": to_world(frame, p["rake_x_offset_cm"], sign * (hw + 150.0),
                                          p["rake_height_cm"]),
                          "rot": {"yaw": yaw + (90.0 if sign < 0 else -90.0), "pitch": 6.0},
                          "cd": p["rake_cd"], "color": color, "inner": 8.0, "outer": 22.0,
                          "radius": 2.5 * hw, "shadows": True, "vsi": 1.5})
    floor = "floor_wet" if "floor_wet" in toggles else ("floor" if "floor" in toggles else None)
    if floor:
        length = 2.0 * pitch_cm
        specs.append({"label": SPAWN_PREFIX + "FLOOR", "kind": "mesh", "mesh": CUBE,
                      "loc": to_world(frame, 0.0, 0.0, 0.0), "yaw": yaw,
                      "scale": (length / 100.0, 2.0 * hw / 100.0, 0.01),
                      "material": {"mid_parent": FLOOR_PARENT,
                                   "scalars": dict(p["floor_wet_scalars"] if floor == "floor_wet"
                                                   else p["floor_scalars"])}})
        if floor == "floor_wet":
            for i, (dx, dy, diam) in enumerate(p["puddles"]):
                specs.append({"label": SPAWN_PREFIX + "PUDDLE_%d" % i, "kind": "mesh", "mesh": CYLINDER,
                              "loc": to_world(frame, dx, dy, 0.6), "yaw": yaw,
                              "scale": (diam / 100.0, 0.7 * diam / 100.0, 0.001),
                              "material": {"mid_parent": FLOOR_PARENT, "scalars": dict(p["puddle_scalars"])}})
    if "strobe" in toggles:
        specs.append({"label": SPAWN_PREFIX + "STROBE", "kind": "spot",
                      "loc": to_world(frame, 150.0, -0.6 * hw, 220.0),
                      "rot": {"yaw": yaw + 60.0, "pitch": -50.0}, "cd": p["strobe_cd"],
                      "color": (0.9, 0.95, 1.0), "inner": 20.0, "outer": 40.0, "radius": 1500.0,
                      "shadows": False, "vsi": 1.0, "strobe": True})
    if "glint" in toggles:
        if not glint or not glint.get("light"):
            raise RuntimeError("LOOK_BENCH_GLINT_UNRESOLVED|no mirror position for this bay")
        specs.append({"label": SPAWN_PREFIX + "GLINT", "kind": "point", "loc": tuple(glint["light"]),
                      "cd": p["glint_cd"], "color": (1.0, 0.9, 0.75), "radius": 2.5 * p["glint_light_dist_cm"],
                      "source_radius": p["glint_source_radius_cm"], "shadows": False, "vsi": 0.5})
        specs.append(_box(SPAWN_PREFIX + "GLINT_BULB", tuple(glint["light"]), yaw, (6.0, 6.0, 9.0),
                          (8.0, 6.5, 4.5, 1.0)))
    if "underpass" in toggles:
        steel, concrete = p["underpass_steel"], p["underpass_concrete"]
        deck_z = float(p["underpass_deck_z_cm"])
        col_y = hw + float(p["underpass_column_outset_cm"])
        u0 = anchor_dx(frame, p, anchor, "underpass_anchor", "underpass_ahead_cm", None)
        for side, sign in (("L", -1.0), ("R", 1.0)):
            specs.append(_box(SPAWN_PREFIX + "UP_PIER_" + side, to_world(frame, u0, sign * col_y, 60.0), yaw,
                              (140.0, 140.0, 120.0), concrete))
            specs.append(_box(SPAWN_PREFIX + "UP_COLUMN_" + side,
                              to_world(frame, u0, sign * col_y, 120.0 + (deck_z - 120.0) / 2.0), yaw,
                              (40.0, 60.0, deck_z - 120.0), steel))
            for k, dx in (("A", -70.0), ("B", 70.0)):
                specs.append(_box(SPAWN_PREFIX + "UP_KNEE_%s_%s" % (side, k),
                                  to_world(frame, u0 + dx, sign * (col_y - 60.0), deck_z - 80.0), yaw,
                                  (120.0, 2.0, 120.0), steel))
        length = max(frame["pitch_cm"], 500.0)
        for side, sign in (("L", -1.0), ("R", 1.0)):
            specs.append(_box(SPAWN_PREFIX + "UP_STRINGER_" + side, to_world(frame, u0, sign * 250.0, deck_z),
                              yaw, (length, 30.0, 30.0), steel))
        ties = int(length // float(p["underpass_tie_every_cm"]))
        for i in range(ties):
            dx = -length / 2.0 + (i + 0.5) * float(p["underpass_tie_every_cm"])
            specs.append(_box(SPAWN_PREFIX + "UP_TIE_%02d" % i, to_world(frame, u0 + dx, 0.0, deck_z + 21.0), yaw,
                              (20.0, 2.0 * col_y, 12.0), steel))
        specs.append({"label": SPAWN_PREFIX + "UP_SHAFT", "kind": "spot",
                      "loc": to_world(frame, u0, 0.0, deck_z + 400.0), "rot": {"yaw": yaw, "pitch": -90.0},
                      "cd": p["underpass_shaft_cd"], "color": (0.85, 0.9, 1.0), "inner": 18.0, "outer": 34.0,
                      "radius": deck_z + 800.0, "shadows": True, "vsi": 3.0})
    if "arch_ring_border" in toggles:
        specs.extend(arch_specs(frame, p, anchor))
    return specs


def needed_pool_labels(frame, states, p, glint):
    out = set()
    for _name, toggles in states:
        for spec in plan_spawns(frame, normalise_toggles(toggles), p, glint):
            out.add(spec["label"])
    return sorted(out)


def plan_light_changes(lights, toggles, p):
    """lights: {id: {"label", "type", "intensity", "visible", fields...}} -> [(id, field, value)]."""
    changes = []
    if "shadows" in toggles:
        keys = sorted((lid for lid, row in lights.items()
                       if row.get("visible") and row.get("type") == "spot" and row.get("intensity", 0) > 0),
                      key=lambda lid: (-lights[lid]["intensity"], lights[lid]["label"]))
        for lid in keys[:int(p["shadow_keys_max"])]:
            changes.append((lid, "cast_shadows", True))
            changes.append((lid, "cast_volumetric_shadow", True))
    if "haze" in toggles:
        for lid in sorted(lights):
            if lights[lid].get("visible"):
                changes.append((lid, "volumetric_scattering_intensity",
                                max(float(lights[lid]["volumetric_scattering_intensity"]), float(p["haze_vsi"]))))
    return changes


def strobe_on(now, start, hz, duty):
    phase = ((now - start) * hz) % 1.0
    return phase < duty


def _plain(v):
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def write_record_verified(path, data, log):
    """Write, flush, fsync, re-read and compare BEFORE anything changes."""
    path = pathlib.Path(path)
    text = json.dumps(data, indent=1, sort_keys=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    back = json.loads(path.read_text(encoding="utf-8"))
    if back != json.loads(text):
        raise RuntimeError("LOOK_BENCH_RECORD_READBACK_MISMATCH|" + str(path))
    log("LOOK_BENCH_ORIGINALS_WRITTEN|path=%s" % path.as_posix())
    return path


def find_prepare_record(bench_dir, explicit=None):
    """The PREPARE record CAPTURE / HOLD / RESTORE / CLEANUP work from: explicit, or newest."""
    if explicit:
        path = pathlib.Path(explicit)
        if not path.is_file():
            raise RuntimeError("LOOK_BENCH_NOT_PREPARED|no record at %s" % path.as_posix())
        return path
    found = sorted(pathlib.Path(bench_dir).glob("*/" + PREPARE_RECORD_NAME))
    if not found:
        raise RuntimeError("LOOK_BENCH_NOT_PREPARED|run PREPARE in the editor world (PIE not running) first")
    return found[-1]


def load_prepare_record(path):
    rec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if rec.get("status") != "spawned":
        raise RuntimeError("LOOK_BENCH_PREPARE_INCOMPLETE|status=%s|%s" % (rec.get("status"), path))
    return rec


class LookBench:
    """Engine-free CAPTURE / HOLD / PROBE logic on a PIE world. `adapter` supplies
    every world operation (make_pie_adapter() in the editor, a fake in the harness).
    It NEVER spawns or destroys: it only places, shows and hides prepared pool
    actors and edits properties."""

    def __init__(self, adapter, record_path, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or utc_stamp()
        self.record = None
        self.strobe = None
        self.strobe_start = 0.0
        self.applied = ()
        self.mid_readback = {}
        self.anchor = None            # camera_anchor() of the clip-start camera (CAPTURE pose phase)
        self.current_specs = []
        self.strobe_hold = False      # bench strobe dark while the settle gate measures

    # ---- read originals, check the pool, write, announce. Nothing changes here. ----
    def read_originals(self, states=None, require_pool=True, prepare_record=None):
        if self.a.world_kind() != "game":
            raise RuntimeError("LOOK_BENCH_NEEDS_PIE|CAPTURE/HOLD/PROBE run on a PIE game world")
        if prepare_record is not None and not same_level(prepare_record.get("world"), self.a.world_name()):
            raise RuntimeError("LOOK_BENCH_WRONG_WORLD|prepared %s, PIE %s" % (prepare_record.get("world"),
                                                                               self.a.world_name()))
        passage, bay = self.p["passage"], int(self.p["bay"])
        ids, lights, frame = resolve_bay(self.a, passage, bay, self.p["half_width_cm"], self.p.get("route_yaw_deg"))
        box = {"frame": frame, "half_len_cm": max(frame["pitch_cm"], 600.0), "half_width_cm": frame["half_width_cm"]}
        edges = self.a.edge_slots(box)
        face = self.a.wing_face(self.p["glint_mesh_contains"], frame) if hasattr(self.a, "wing_face") else None
        glint = None
        if face:
            glint = _plain(glint_solution(tuple(face["point"]), tuple(face["normal"]), frame, self.p))
            glint["face"] = face
        if len(edges) > int(self.p["edge_max_components"]):
            raise RuntimeError("LOOK_BENCH_TOO_MANY_EDGE_SLOTS|%d" % len(edges))
        if states is None:
            states = default_states(bool(glint and glint.get("light")))
        states = [(n, normalise_toggles(t)) for n, t in states]
        needed = needed_pool_labels(frame, states, self.p, glint)    # raises GLINT_UNRESOLVED before any write
        pool = []
        if require_pool:
            pool = self.a.pool_labels()
            missing = [l for l in needed if l not in pool]
            if missing:
                raise RuntimeError("LOOK_BENCH_PREPARED_MISSING|%d|%s|run PREPARE in the editor world before PIE"
                                   % (len(missing), ",".join(missing[:6])))
            lit = [l for l in pool if self.a.pool_state(l)["on"]]
            if lit:
                raise RuntimeError("LOOK_BENCH_POOL_NOT_BASE|%d|%s|run RESTORE first" % (len(lit), ",".join(lit[:6])))
        census = self.a.census()
        strobes = self.a.show_strobes() if hasattr(self.a, "show_strobes") else []
        self.record = {
            "run": self.run_id, "written_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "world": self.a.world_name(), "passage": passage, "bay": bay,
            "params": _plain(self.p), "frame": _plain(frame),
            "lights": {lid: {k: lights[lid][k] for k in ("label",) + LIGHT_FIELDS} for lid in ids},
            "light_meta": {lid: {"type": lights[lid]["type"], "intensity": lights[lid]["intensity"],
                                 "visible": lights[lid]["visible"], "units": lights[lid].get("units")}
                           for lid in ids},
            "show_strobes": strobes,
            "edge_slots": edges,
            "cvars": {STREAM_CVAR: self.a.get_cvar(STREAM_CVAR)},
            "census_before": census,
            "spawn_prefix": SPAWN_PREFIX,
            "glint": glint,
            "states": [[n, list(t)] for n, t in states],
            "pool_needed": needed,
            "pool_present": sorted(pool),
            "prepare_run": (prepare_record or {}).get("run"),
        }
        write_record_verified(self.record_path, self.record, self.a.log)
        self.a.note("record_written")
        self.a.log("LOOK_BENCH_EDGE_SLOTS|run=%s|%s bay %d|edge_slots=%d%s" % (
            self.run_id, passage, bay, len(edges), "|edge toggle is a NO-OP in this bay" if not edges else ""))
        self.a.log("LOOK_BENCH_ANNOUNCE|run=%s|world=PIE|%s bay %d|uses %d prepared %s* pool actors (no spawns); "
                   "restore at end|record=%s" % (self.run_id, passage, bay, len(needed), SPAWN_PREFIX,
                                                 self.record_path.as_posix()))
        return self.record

    def _lights(self):
        out = {}
        for lid, row in self.record["lights"].items():
            meta = self.record["light_meta"][lid]
            out[lid] = dict(row, **meta)
        return out

    def _frame(self):
        frame = dict(self.record["frame"])
        for k in ("origin", "fwd", "right"):
            frame[k] = tuple(frame[k])
        return frame

    # ---- state changes ----
    def to_base(self):
        self.strobe = None
        for label in self.a.pool_labels():
            if self.a.pool_state(label)["on"]:
                self.a.hide_pool(label)
        for lid, row in self.record["lights"].items():
            for field in LIGHT_FIELDS:
                if self.a.read_light(lid)[field] != row[field]:
                    self.a.set_light(lid, field, row[field])
        for slot in self.record["edge_slots"]:
            if self.a.slot_material(slot["id"], slot["slot"]) != slot["material"]:
                self.a.set_slot_material(slot["id"], slot["slot"], {"path": slot["material"]})
        self.applied = ()

    def set_anchor(self, cam_loc, fov_deg=None, aspect=None):
        self.anchor = camera_anchor(self._frame(), cam_loc, self.p, fov_deg, aspect)
        return self.anchor

    # ---- show strobes (AInfinityStageStrobeLight): off for a CAPTURE, restored after ----
    def neutralise_show_strobes(self):
        if self.record is None or not self.record_path.is_file():
            raise RuntimeError("LOOK_BENCH_NO_RECORD|originals must be on disk before any change")
        n = 0
        for row in self.record.get("show_strobes", []):
            if row["enabled"]:
                self.a.set_show_strobe(row["id"], False)
                if self.a.show_strobe_enabled(row["id"]):
                    raise RuntimeError("LOOK_BENCH_STROBE_OFF_FAILED|" + row["label"])
                n += 1
        self.a.log("LOOK_BENCH_SHOW_STROBES_OFF|run=%s|disabled=%d|%s" % (
            self.run_id, n, ",".join(r["label"] for r in self.record.get("show_strobes", [])) or "none"))
        return n

    def apply(self, toggles, now=0.0, hold_strobe=False):
        if self.record is None or not self.record_path.is_file():
            raise RuntimeError("LOOK_BENCH_NO_RECORD|originals must be on disk before any change")
        toggles = normalise_toggles(toggles)
        specs = plan_spawns(self._frame(), toggles, self.p, self.record.get("glint"), self.anchor)
        self.current_specs = specs
        self.strobe_hold = bool(hold_strobe)
        pool = set(self.a.pool_labels())
        missing = [s["label"] for s in specs if s["label"] not in pool]
        if missing:
            raise RuntimeError("LOOK_BENCH_PREPARED_MISSING|%d|%s" % (len(missing), ",".join(missing[:6])))
        self.to_base()
        for lid, field, value in plan_light_changes(self._lights(), toggles, self.p):
            self.a.set_light(lid, field, value)
        shown = 0
        for spec in specs:
            self.a.show_pool(spec)
            shown += 1
            if spec.get("strobe"):
                self.strobe = (spec["label"], spec["cd"])
                self.strobe_start = now
            if "material" in spec and spec["material"].get("scalars"):
                self.mid_readback[spec["label"]] = self.a.material_readback(spec["label"])
        n_edges = len(self.record["edge_slots"])
        if "edge" in toggles:
            for slot in self.record["edge_slots"]:
                self.a.set_slot_material(slot["id"], slot["slot"],
                                         {"mid_parent": EDGE_PARENT,
                                          "vectors": {"Color": tuple(self.p["edge_color"])}})
            if not n_edges:
                self.a.log("LOOK_BENCH_EDGE_NOOP|run=%s|toggles=%s|edge_slots=0|the edge toggle changed NOTHING "
                           "in this bay" % (self.run_id, ",".join(toggles)))
        self.applied = toggles
        self.a.log("LOOK_BENCH_STATE|run=%s|toggles=%s|shown=%d|edge_slots=%d|edge_effective=%s" % (
            self.run_id, ",".join(toggles) or "base", shown, n_edges, bool("edge" in toggles and n_edges)))

    def release_strobe(self, now):
        self.strobe_hold = False
        self.strobe_start = now

    def tick(self, now):
        if self.strobe:
            label, cd = self.strobe
            lit = (not self.strobe_hold) and strobe_on(now, self.strobe_start, self.p["strobe_hz"], self.p["strobe_duty"])
            self.a.set_pool_intensity(label, cd if lit else 0.0)

    # ---- restore + exact verification ----
    def restore(self):
        self.to_base()
        for row in self.record.get("show_strobes", []) if self.record else []:
            if self.a.show_strobe_enabled(row["id"]) != row["enabled"]:
                self.a.set_show_strobe(row["id"], row["enabled"])
        problems = self.verify()
        if self.record:
            want = self.record["cvars"][STREAM_CVAR]
            if self.a.get_cvar(STREAM_CVAR) != want:
                self.a.set_cvar(STREAM_CVAR, want)
            if self.a.get_cvar(STREAM_CVAR) != want:
                problems.append("cvar %s" % STREAM_CVAR)
        return problems

    def verify(self):
        problems = []
        for lid, row in self.record["lights"].items():
            now = self.a.read_light(lid)
            for field in LIGHT_FIELDS:
                if now[field] != row[field]:
                    problems.append("%s %s %r != %r" % (row["label"], field, now[field], row[field]))
        for slot in self.record["edge_slots"]:
            got = self.a.slot_material(slot["id"], slot["slot"])
            if got != slot["material"]:
                problems.append("edge %s[%d] %s != %s" % (slot["id"], slot["slot"], got, slot["material"]))
        lit = [l for l in self.a.pool_labels() if self.a.pool_state(l)["on"]]
        if lit:
            problems.append("pool actors still shown %s" % ",".join(sorted(lit)))
        for row in self.record.get("show_strobes", []):
            if self.a.show_strobe_enabled(row["id"]) != row["enabled"]:
                problems.append("show strobe %s enabled != %r" % (row["label"], row["enabled"]))
        return problems


def restore_from_record(adapter, record_path):
    """RESTORE: crash recovery from one capture record alone. Hides the pool; never destroys."""
    record = json.loads(pathlib.Path(record_path).read_text(encoding="utf-8"))
    bench = LookBench(adapter, record_path, record.get("params"), record.get("run"))
    bench.record = record
    return bench.restore()


def restore_all(adapter, records, log):
    """Newest capture record first, so the OLDEST originals are the last written."""
    problems = []
    for path in sorted((pathlib.Path(r) for r in records), key=lambda r: r.as_posix(), reverse=True):
        got = restore_from_record(adapter, path)
        log("LOOK_BENCH_RESTORED_RECORD|%s|problems=%d" % (path.as_posix(), len(got)))
        problems.extend(got)
    for label in adapter.pool_labels():          # no capture record at all: still leave the pool dark
        if adapter.pool_state(label)["on"]:
            adapter.hide_pool(label)
    lit = [l for l in adapter.pool_labels() if adapter.pool_state(l)["on"]]
    if lit:
        problems.append("pool actors still shown %s" % ",".join(sorted(lit)))
    return problems


class PrepareBench:
    """PREPARE (editor world, PIE not running): spawn the whole hidden pool."""

    def __init__(self, adapter, record_path, bays=None, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.bays = [dict(b) for b in (bays or self.p["prepare_bays"])]
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or utc_stamp()
        self.record = None

    def plan(self):
        specs = {}
        bays = []
        for bay_params in self.bays:
            p = dict(self.p)
            p.update(bay_params)
            ids, _lights, frame = resolve_bay(self.a, p["passage"], int(p["bay"]), p["half_width_cm"], p.get("route_yaw_deg"))
            dummy_glint = {"light": list(to_world(frame, 0.0, 0.0, 500.0))}   # placed for real in PIE
            for spec in plan_spawns(frame, ALL_TOGGLES, p, dummy_glint):
                specs.setdefault(spec["label"], spec)
            bays.append({"passage": p["passage"], "bay": int(p["bay"]), "lights": len(ids), "frame": _plain(frame)})
        ties = sorted(l for l in specs if l.startswith(SPAWN_PREFIX + "UP_TIE_"))
        if ties:
            template = specs[ties[-1]]
            for i in range(len(ties), len(ties) + int(self.p["pool_tie_margin"])):
                spare = dict(template, label=SPAWN_PREFIX + "UP_TIE_%02d" % i)
                specs[spare["label"]] = spare
        return specs, bays

    def run(self):
        kind = self.a.world_kind()
        if kind != "editor":
            raise RuntimeError("LOOK_BENCH_PREPARE_NEEDS_EDITOR|world=%s|end PIE first; PREPARE never touches PIE"
                               % kind)
        census = self.a.census()
        if census["maps"] or census["content"]:
            raise RuntimeError("LOOK_BENCH_DIRTY_BEFORE_PREPARE|%r|a Don't-Save restart must lose nothing" % census)
        left = self.a.bench_actor_labels(SPAWN_PREFIX)
        if left:
            raise RuntimeError("LOOK_BENCH_LEFTOVERS|%d|run CLEANUP or a Don't-Save restart first" % len(left))
        specs, bays = self.plan()
        labels = sorted(specs)
        self.record = {
            "run": self.run_id, "written_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "world": self.a.world_name(), "census_before": census, "leftovers_before": left,
            "tag": POOL_TAG, "spawn_prefix": SPAWN_PREFIX, "bays": bays, "params": _plain(self.p),
            "pool": [{"label": l, "kind": specs[l]["kind"], "mesh": specs[l].get("mesh"),
                      "material_parent": specs[l].get("material", {}).get("mid_parent")} for l in labels],
            "spawned": {}, "status": "planned",
        }
        write_record_verified(self.record_path, self.record, self.a.log)
        self.a.note("record_written")
        self.a.log("LOOK_BENCH_ANNOUNCE|run=%s|world=EDITOR|spawning %d hidden %s* actors (tag %s) into the editor "
                   "world; they stay until a Don't-Save restart or CLEANUP; the map WILL be dirty and must NOT be "
                   "saved|record=%s" % (self.run_id, len(labels), SPAWN_PREFIX, POOL_TAG, self.record_path.as_posix()))
        complete = False
        try:
            for label in labels:
                self.record["spawned"][label] = self.a.spawn_hidden(specs[label])
            complete = True
        finally:
            after = self.a.census()
            self.record["status"] = "spawned" if complete else "partial"
            self.record["census_after"] = after
            self.record["dirtied_by_prepare"] = {
                "maps": sorted(set(after["maps"]) - set(census["maps"])),
                "content": sorted(set(after["content"]) - set(census["content"]))}
            write_record_verified(self.record_path, self.record, self.a.log)
            self.a.log("%s|run=%s|editor world holds %s* actors and a dirty map; discard both with a Don't-Save "
                       "restart (never Save All)" % (RESTART_MARKER, self.run_id, SPAWN_PREFIX))
        problems = []
        present = set(self.a.pool_labels())
        if present != set(labels):
            problems.append("pool mismatch: missing %s extra %s" % (sorted(set(labels) - present),
                                                                    sorted(present - set(labels))))
        problems += ["%s not hidden" % l for l in labels if l in present and self.a.pool_state(l)["on"]]
        if problems:
            raise RuntimeError("LOOK_BENCH_PREPARE_VERIFY|%r" % problems)
        kinds = {}
        for label in labels:
            kinds[specs[label]["kind"]] = kinds.get(specs[label]["kind"], 0) + 1
        self.a.log("LOOK_BENCH_PREPARED|run=%s|actors=%d|%s|bays=%s|record=%s" % (
            self.run_id, len(labels), "|".join("%s=%d" % kv for kv in sorted(kinds.items())),
            ",".join("%s/%d" % (b["passage"], b["bay"]) for b in bays), self.record_path.as_posix()))
        return self.record


def cleanup(adapter, prepare_record_path):
    """CLEANUP (editor world, PIE not running): delete the tagged pool WITHOUT saving.
    Refuses, deleting nothing, if any dirty package is not one PREPARE dirtied."""
    if adapter.world_kind() != "editor":
        raise RuntimeError("LOOK_BENCH_CLEANUP_NEEDS_EDITOR|world=%s|end PIE first" % adapter.world_kind())
    record = json.loads(pathlib.Path(prepare_record_path).read_text(encoding="utf-8"))
    allowed = record.get("dirtied_by_prepare")
    if allowed is None:
        raise RuntimeError("LOOK_BENCH_CLEANUP_NO_CENSUS|record has no dirtied_by_prepare; use a Don't-Save restart")
    now = adapter.census()
    foreign = ([m for m in now["maps"] if m not in allowed["maps"]]
               + [c for c in now["content"] if c not in allowed["content"]])
    if foreign:
        raise RuntimeError("LOOK_BENCH_CLEANUP_FOREIGN_DIRTY|%s|nothing deleted" % ",".join(foreign))
    untagged = sorted(set(adapter.bench_actor_labels(SPAWN_PREFIX)) - set(adapter.pool_labels()))
    deleted = 0
    for label in adapter.pool_labels():
        adapter.destroy_pool(label)
        deleted += 1
    left = adapter.pool_labels()
    if left:
        raise RuntimeError("LOOK_BENCH_CLEANUP_LEFT|%s" % ",".join(left))
    adapter.log("LOOK_BENCH_CLEANUP_OK|deleted=%d|untagged_prefix_actors_left=%s|record=%s" % (
        deleted, ",".join(untagged) or "none", pathlib.Path(prepare_record_path).as_posix()))
    adapter.log("%s|map still dirty after CLEANUP; never save it" % RESTART_MARKER)
    return deleted


def frame_stats(deltas):
    """Editor tick deltas (s) -> ms stats. Includes Slate/editor cost; compare states, not absolutes."""
    ms = sorted(1000.0 * d for d in deltas if d > 0)
    if not ms:
        return {"n": 0}
    pick = lambda q: ms[min(len(ms) - 1, int(q * (len(ms) - 1) + 0.5))]
    return {"n": len(ms), "mean": sum(ms) / len(ms), "p50": pick(0.5), "p95": pick(0.95), "max": ms[-1],
            "over_40ms": sum(1 for m in ms if m > 40.0)}


def clip_plan(pass_frame, p):
    start = int(pass_frame - p["lead_seconds"] * TICKS_PER_SECOND)
    end = int(start + p["clip_seconds"] * TICKS_PER_SECOND)
    step = int(TICKS_PER_SECOND / float(p["clip_fps"]))
    return {"start": start, "end": end, "step": step,
            "frames_expected": int(math.ceil((end - start) / float(step)))}


# ---- luma settle gate (pure: no PIL / numpy inside the editor) ----

def png_luma(path):
    """Mean Rec.709 luma of an 8-bit non-interlaced PNG (grey, grey+alpha, RGB, RGBA), on the
    stored sRGB values 0-255. Raises on anything else or on a truncated / half-written file
    (HighResShot writes asynchronously: the caller retries)."""
    data = pathlib.Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("LOOK_BENCH_PNG|not a PNG")
    pos, idat, head, ended = 8, [], None, False
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if len(body) != n:
            raise ValueError("LOOK_BENCH_PNG|truncated chunk")
        pos += 12 + n
        if typ == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            ended = True
            break
    if head is None or not ended:
        raise ValueError("LOOK_BENCH_PNG|incomplete")
    w, h, depth, ctype, _comp, _filt, interlace = head
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        raise ValueError("LOOK_BENCH_PNG|unsupported depth=%d type=%d interlace=%d" % (depth, ctype, interlace))
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    if len(raw) != h * (stride + 1):
        raise ValueError("LOOK_BENCH_PNG|size mismatch")
    prev = bytearray(stride)
    sr = sg = sb = 0
    for y in range(h):
        base = y * (stride + 1)
        ftype = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        elif ftype != 0:
            raise ValueError("LOOK_BENCH_PNG|bad filter %d" % ftype)
        if ctype in (0, 4):
            v = sum(line[0::bpp])
            sr, sg, sb = sr + v, sg + v, sb + v
        else:
            sr += sum(line[0::bpp])
            sg += sum(line[1::bpp])
            sb += sum(line[2::bpp])
        prev = line
    n = float(w * h)
    return (0.2126 * sr + 0.7152 * sg + 0.0722 * sb) / n


def settle_decision(samples, elapsed, p):
    """samples: [[t, luma], ...] in probe order. 'stable' when the last settle_window samples
    lie within max(settle_tol_abs, settle_tol_rel * mean) and elapsed >= settle_min_seconds;
    'timeout' once elapsed > settle_max_seconds without that; else 'wait'."""
    k = int(p["settle_window"])
    if len(samples) >= k and elapsed >= float(p["settle_min_seconds"]):
        last = [float(s[1]) for s in samples[-k:]]
        mean = sum(last) / k
        if max(last) - min(last) <= max(float(p["settle_tol_abs"]), float(p["settle_tol_rel"]) * mean):
            return "stable"
    if elapsed > float(p["settle_max_seconds"]):
        return "timeout"
    return "wait"


def base_return_ok(luma, ref, p):
    return abs(float(luma) - float(ref)) <= max(float(p["base_return_tol_abs"]),
                                                float(p["base_return_tol_rel"]) * float(ref))


# ---- frustum check (pure) ----

def project(cam, point):
    """Camera {loc, rot{yaw,pitch,roll}, fov_deg (horizontal), aspect} -> (ndc_x, ndc_y, depth),
    ndc in [-1, 1] inside the view; None behind the near plane (10 cm). UE camera: X fwd, Y right, Z up."""
    fx, ry, uz = rotator_axes(cam["rot"]["yaw"], cam["rot"]["pitch"], cam["rot"]["roll"])
    d = _sub(point, cam["loc"])
    depth = _dot(d, fx)
    if depth < 10.0:
        return None
    th = math.tan(math.radians(float(cam["fov_deg"])) / 2.0)
    tv = th / float(cam["aspect"])
    return (_dot(d, ry) / depth / th, _dot(d, uz) / depth / tv, depth)


def in_view(cam, point):
    got = project(cam, point)
    return got is not None and abs(got[0]) <= 1.0 and abs(got[1]) <= 1.0


def spec_points(spec):
    """Centre plus, for boxes / cylinders, the 8 corners (scale x 100 cm base, Rotator(roll, 0, yaw))."""
    c = tuple(spec["loc"])
    if spec["kind"] != "mesh":
        return [c]
    ax, ay, az = rotator_axes(spec.get("yaw", 0.0), 0.0, spec.get("roll", 0.0))
    hx, hy, hz = (50.0 * float(v) for v in spec["scale"])
    pts = [c]
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                pts.append(_add(c, _add(_mul(ax, sx * hx), _add(_mul(ay, sy * hy), _mul(az, sz * hz)))))
    return pts


def view_count(specs, cams):
    """Mesh + fog specs with any point inside ANY of the camera poses. Lights are not counted."""
    checkable = [s for s in specs if s["kind"] in ("mesh", "fog")]
    seen = sorted(s["label"] for s in checkable if any(in_view(c, pt) for c in cams for pt in spec_points(s)))
    return {"n_visible": len(seen), "n_checkable": len(checkable), "visible": seen}


def view_gate(toggles, specs, cams, p):
    """Per-state frustum gate. arch_ring_border needs >= arch_min_visible_frac of its segments in
    view; underpass needs a column AND a deck member (stringer or tie). Other toggles: logged only.
    Frustum only: occlusion by wings / ceiling tops is NOT checked (no ray casts here)."""
    got = view_count(specs, cams)
    vis = set(got["visible"])
    fails = []
    if "arch_ring_border" in toggles:
        arch = [s["label"] for s in specs if s["label"].startswith(SPAWN_PREFIX + "ARCH_")]
        n_arch = sum(1 for l in arch if l in vis)
        need = int(math.ceil(float(p["arch_min_visible_frac"]) * len(arch)))
        got["arch_visible"] = n_arch
        got["arch_needed"] = need
        if n_arch < need:
            fails.append("arch %d/%d < %d" % (n_arch, len(arch), need))
    if "underpass" in toggles:
        cols = sum(1 for l in vis if l.startswith(SPAWN_PREFIX + "UP_COLUMN_"))
        deck = sum(1 for l in vis if l.startswith((SPAWN_PREFIX + "UP_STRINGER_", SPAWN_PREFIX + "UP_TIE_")))
        got["underpass_columns"] = cols
        got["underpass_deck"] = deck
        if not cols or not deck:
            fails.append("underpass columns=%d deck=%d" % (cols, deck))
    got["fails"] = fails
    got["ok"] = not fails
    return got


def route_deviation_deg(frame, cam_locs):
    """Angle between the clip camera's travel (first -> last location) and the frame's fwd.
    None when the camera moved < 50 cm (nothing to compare)."""
    if len(cam_locs) < 2:
        return None
    dx, dy = cam_locs[-1][0] - cam_locs[0][0], cam_locs[-1][1] - cam_locs[0][1]
    if math.hypot(dx, dy) < 50.0:
        return None
    a = math.degrees(math.atan2(dy, dx) - math.atan2(frame["fwd"][1], frame["fwd"][0]))
    return abs((a + 180.0) % 360.0 - 180.0)


# --------------------------------------------------------------------------
# Unreal side. Everything below runs only inside the editor.
# --------------------------------------------------------------------------

def _world_common(unreal, world, handles, events):
    """Read-side operations shared by the editor and PIE adapters (closure-held UE refs)."""
    tag = unreal.Name(POOL_TAG)

    def all_actors():
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))

    def get(key):
        obj = handles.get(key)
        if obj is None:
            obj = unreal.find_object(None, key)
            if obj is None:
                raise RuntimeError("LOOK_BENCH_UNRESOLVED|" + key)
            handles[key] = obj
        return obj

    def comp_of(actor):
        comps = list(actor.get_components_by_class(unreal.LightComponent))
        return comps[0] if len(comps) == 1 else None

    def pool_map():
        out = {}
        for actor in all_actors():
            label = actor.get_actor_label()
            if label.startswith(SPAWN_PREFIX) and actor.actor_has_tag(tag):
                if label in out:
                    raise RuntimeError("LOOK_BENCH_POOL_DUPLICATE|" + label)
                out[label] = actor
        handles["pool"] = out
        return out

    def pool_actor(label):
        pool = handles.get("pool") or pool_map()
        actor = pool.get(label)
        if actor is None:
            actor = pool_map().get(label)
        if actor is None:
            raise RuntimeError("LOOK_BENCH_PREPARED_MISSING|1|" + label)
        return actor

    def main_comp(actor):
        if isinstance(actor, unreal.SpotLight):
            return "spot", actor.get_component_by_class(unreal.SpotLightComponent)
        if isinstance(actor, unreal.PointLight):
            return "point", actor.get_component_by_class(unreal.PointLightComponent)
        if isinstance(actor, unreal.LocalFogVolume):
            return "fog", actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        return "mesh", actor.static_mesh_component

    class Common:
        def world_name(self):
            return world.get_path_name() if world else None

        def note(self, event):
            events.append(event)

        def log(self, message):
            unreal.log(message)

        def census(self):
            maps = sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
            content = sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
            return {"maps": maps, "content": content}

        def find_lights(self, prefixes):
            ids = []
            for actor in all_actors():
                label = actor.get_actor_label()
                if label.startswith(tuple(prefixes)) and comp_of(actor) is not None:
                    lid = actor.get_path_name()
                    handles[lid] = actor
                    ids.append(lid)
            return sorted(ids)

        def read_light(self, lid):
            actor = get(lid)
            comp = comp_of(actor)
            loc = actor.get_actor_location()
            try:
                units = str(comp.get_editor_property("intensity_units"))
            except Exception:                 # not a local light (no IntensityUnits)
                units = None
            kind = ("spot" if isinstance(comp, unreal.SpotLightComponent) else
                    "rect" if isinstance(comp, unreal.RectLightComponent) else
                    "point" if isinstance(comp, unreal.PointLightComponent) else "other")
            return {"label": actor.get_actor_label(), "type": kind,
                    "location": (float(loc.x), float(loc.y), float(loc.z)),
                    "intensity": float(comp.get_editor_property("intensity")), "units": units,
                    "visible": bool(comp.is_visible()),
                    "cast_shadows": bool(comp.get_editor_property("cast_shadows")),
                    "cast_volumetric_shadow": bool(comp.get_editor_property("cast_volumetric_shadow")),
                    "volumetric_scattering_intensity": float(
                        comp.get_editor_property("volumetric_scattering_intensity"))}

        def bench_actor_labels(self, prefix):
            return sorted(a.get_actor_label() for a in all_actors() if a.get_actor_label().startswith(prefix))

        def pool_labels(self):
            return sorted(pool_map())

        def pool_state(self, label):
            kind, comp = main_comp(pool_actor(label))
            on = bool(comp.is_visible())
            out = {"kind": kind, "visible": on}
            if kind in ("spot", "point"):
                out["intensity"] = float(comp.get_editor_property("intensity"))
                on = on or out["intensity"] > 0.0
            out["on"] = on
            return out

        def get_cvar(self, name):
            return int(unreal.SystemLibrary.get_console_variable_int_value(name))

    return Common, all_actors, get, comp_of, pool_actor, main_comp


def make_editor_adapter(unreal):
    """PREPARE / CLEANUP: the EDITOR world, only while no PIE world exists."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = editor_sub.get_editor_world()
    handles = {}
    events = []
    Common, _all, _get, _comp_of, pool_actor, main_comp = _world_common(unreal, world, handles, events)

    class EditorAdapter(Common):
        def world_kind(self):
            if editor_sub.get_game_world() is not None:
                return "pie_running"
            return "editor" if world is not None else None

        def spawn_hidden(self, spec):
            events.append(("spawn", spec["label"]))
            loc = unreal.Vector(*spec["loc"])
            kind = spec["kind"]
            cls = {"spot": unreal.SpotLight, "point": unreal.PointLight,
                   "fog": unreal.LocalFogVolume}.get(kind, unreal.StaticMeshActor)
            actor = actor_sub.spawn_actor_from_class(cls, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            if actor is None:
                raise RuntimeError("LOOK_BENCH_SPAWN_FAILED|" + spec["label"])
            if actor.get_world() != world:
                actor_sub.destroy_actor(actor)
                raise RuntimeError("LOOK_BENCH_SPAWN_NOT_IN_EDITOR_WORLD|" + spec["label"])
            actor.set_actor_label(spec["label"], False)
            actor.set_editor_property("tags", [unreal.Name(POOL_TAG)])
            actor.set_actor_enable_collision(False)
            _kind, comp = main_comp(actor)
            if kind in ("spot", "point"):
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_intensity_units(unreal.LightUnits.CANDELAS)
                comp.set_intensity(0.0)
                comp.set_cast_shadows(False)
            elif kind == "fog":
                comp.set_radial_fog_extinction(0.0)
                comp.set_height_fog_extinction(0.0)
            else:
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_static_mesh(unreal.load_object(None, spec["mesh"]))
                parent = spec.get("material", {}).get("mid_parent")
                if parent:
                    comp.set_material(0, unreal.load_object(None, parent))   # plain asset ref; MIDs made in PIE
            actor.get_editor_property("root_component").set_mobility(unreal.ComponentMobility.MOVABLE)
            comp.set_visibility(False, True)
            actor.set_actor_hidden_in_game(True)
            actor.set_is_temporarily_hidden_in_editor(True)
            handles.pop("pool", None)
            return actor.get_path_name()

        def destroy_pool(self, label):
            events.append(("destroy", label))
            actor = pool_actor(label)
            if not actor_sub.destroy_actor(actor):
                raise RuntimeError("LOOK_BENCH_DESTROY_FAILED|" + label)
            handles.pop("pool", None)

    adapter = EditorAdapter()
    adapter.events = events
    return adapter


# ---- PIE ADAPTER BEGIN (no spawn / destroy / editor-actor API may appear in this region) ----
def make_pie_adapter(unreal):
    """CAPTURE / HOLD / RESTORE / PROBE: the PIE game world. Places, shows, hides
    and edits prepared pool actors; it has no way to create or remove actors."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor_sub.get_game_world()
    handles = {}
    events = []
    Common, all_actors, get, _comp_of, pool_actor, main_comp = _world_common(unreal, world, handles, events)

    def make_mid(spec):
        parent = unreal.load_object(None, spec["mid_parent"])
        # UE 5.8 Python exposes no KismetMaterialLibrary (measured 5 Oct); MaterialLibrary is the Python name of the
        # same UKismetMaterialLibrary, else fall back to MaterialInstanceDynamic.create.
        lib = getattr(unreal, "MaterialLibrary", None) or getattr(unreal, "KismetMaterialLibrary", None)
        if lib is not None and hasattr(lib, "create_dynamic_material_instance"):
            mid = lib.create_dynamic_material_instance(world, parent)
        else:
            mid = unreal.MaterialInstanceDynamic.create(parent, None)
        for name, value in spec.get("scalars", {}).items():
            mid.set_scalar_parameter_value(name, float(value))
        for name, value in spec.get("vectors", {}).items():
            mid.set_vector_parameter_value(name, unreal.LinearColor(*value))
        return mid

    class PieAdapter(Common):
        def world_kind(self):
            return "game" if world is not None else None

        def set_light(self, lid, field, value):
            events.append(("set_light", lid, field))
            comp = _comp_of(get(lid))
            # UFUNCTION setters only: they mark render state, not the package.
            if field == "cast_shadows":
                comp.set_cast_shadows(bool(value))
            elif field == "cast_volumetric_shadow":
                comp.set_cast_volumetric_shadow(bool(value))
            elif field == "volumetric_scattering_intensity":
                comp.set_volumetric_scattering_intensity(float(value))
            else:
                raise RuntimeError("LOOK_BENCH_FIELD|" + field)

        def edge_slots(self, box):
            frame = box["frame"]
            ox, oy, _ = frame["origin"]
            fx, fy = frame["fwd"]
            rows = []
            for actor in all_actors():
                if actor.get_actor_label().startswith(SPAWN_PREFIX):
                    continue
                for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                    idx = comp.get_material_index("Edge")
                    if idx < 0:
                        continue
                    origin, _extent, _radius = unreal.SystemLibrary.get_component_bounds(comp)
                    dx, dy = origin.x - ox, origin.y - oy
                    along, across = dx * fx + dy * fy, -dx * fy + dy * fx
                    if abs(along) > box["half_len_cm"] or abs(across) > box["half_width_cm"] + 400.0:
                        continue
                    cid = comp.get_path_name()
                    handles[cid] = comp
                    mat = comp.get_material(idx)
                    rows.append({"id": cid, "slot": int(idx), "material": mat.get_path_name() if mat else None})
            return sorted(rows, key=lambda r: (r["id"], r["slot"]))

        def wing_face(self, contains, frame):
            """Front-face centre and normal of the instance nearest the bay of a flat whose
            mesh path contains `contains`. Flat V3 fronts face local -X (FlatV3Spec:179-180)."""
            ox, oy, _ = frame["origin"]
            best = None
            for actor in all_actors():
                for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                    mesh = comp.get_editor_property("static_mesh")
                    if mesh is None or contains not in mesh.get_path_name():
                        continue
                    xforms = []
                    if isinstance(comp, unreal.InstancedStaticMeshComponent):
                        for i in range(comp.get_instance_count()):
                            got = comp.get_instance_transform(i, True)
                            xforms.append(got[-1] if isinstance(got, tuple) else got)
                    else:
                        xforms.append(comp.get_world_transform())
                    bounds = mesh.get_bounds()
                    o, e = bounds.origin, bounds.box_extent
                    local = unreal.Vector(o.x - e.x, o.y, o.z)
                    for xf in xforms:
                        pt = unreal.MathLibrary.transform_location(xf, local)
                        d = math.hypot(pt.x - ox, pt.y - oy)
                        if best is None or d < best[0]:
                            nrm = unreal.MathLibrary.transform_direction(xf, unreal.Vector(-1.0, 0.0, 0.0))
                            best = (d, {"point": [float(pt.x), float(pt.y), float(pt.z)],
                                        "normal": [float(nrm.x), float(nrm.y), float(nrm.z)],
                                        "mesh": mesh.get_path_name(), "component": comp.get_path_name(),
                                        "distance_from_bay_cm": float(d)})
            if best is None or best[0] > 3000.0:
                return None
            return best[1]

        def camera_location(self):
            cam = unreal.GameplayStatics.get_player_camera_manager(world, 0)
            loc = cam.get_camera_location() if cam else None
            return [float(loc.x), float(loc.y), float(loc.z)] if loc else None

        def camera_pose(self, aspect, fov_fallback):
            """APlayerCameraManager GetCameraLocation / GetCameraRotation / GetFOVAngle
            (UFUNCTION BlueprintCallable, PlayerCameraManager.h:663,701,705)."""
            cam = unreal.GameplayStatics.get_player_camera_manager(world, 0)
            if cam is None:
                return None
            loc, rot = cam.get_camera_location(), cam.get_camera_rotation()
            fov = float(cam.get_fov_angle() or 0.0)
            return {"loc": [float(loc.x), float(loc.y), float(loc.z)],
                    "rot": {"yaw": float(rot.yaw), "pitch": float(rot.pitch), "roll": float(rot.roll)},
                    "fov_deg": fov if fov > 1.0 else float(fov_fallback), "fov_read": fov, "aspect": float(aspect)}

        def show_strobes(self):
            cls = getattr(unreal, "InfinityStageStrobeLight", None)
            if cls is None:
                return []
            rows = []
            for actor in unreal.GameplayStatics.get_all_actors_of_class(world, cls):
                sid = actor.get_path_name()
                handles[sid] = actor
                rows.append({"id": sid, "label": actor.get_actor_label(),
                             "enabled": bool(actor.get_editor_property("strobe_enabled"))})
            return sorted(rows, key=lambda r: r["id"])

        def show_strobe_enabled(self, sid):
            return bool(get(sid).get_editor_property("strobe_enabled"))

        def set_show_strobe(self, sid, enabled):
            """bStrobeEnabled has no UFUNCTION setter; NEVER notify = no Modify / PostEditChange
            (EPropertyAccessChangeNotifyMode, PropertyAccessUtil.h:51-57). Tick reads it every frame."""
            events.append(("set_strobe", sid))
            get(sid).set_editor_property("strobe_enabled", bool(enabled),
                                         notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

        def slot_material(self, cid, slot):
            mat = get(cid).get_material(slot)
            return mat.get_path_name() if mat else None

        def set_slot_material(self, cid, slot, spec):
            events.append(("set_slot", cid, slot))
            if "path" in spec:
                mat = unreal.load_object(None, spec["path"]) if spec["path"] else None
            else:
                mat = make_mid(spec)
            get(cid).set_material(slot, mat)

        def show_pool(self, spec):
            """Place a prepared actor at the spec, set its properties, then make it visible."""
            events.append(("show", spec["label"]))
            actor = pool_actor(spec["label"])
            kind, comp = main_comp(actor)
            if kind != spec["kind"]:
                raise RuntimeError("LOOK_BENCH_POOL_KIND|%s is %s, spec wants %s" % (spec["label"], kind, spec["kind"]))
            if kind == "spot":
                rot = unreal.Rotator(roll=0.0, pitch=spec["rot"]["pitch"], yaw=spec["rot"]["yaw"])
            elif kind == "point":
                rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
            else:
                rot = unreal.Rotator(roll=float(spec.get("roll", 0.0)), pitch=0.0, yaw=spec["yaw"])
            loc = unreal.Vector(*spec["loc"])
            actor.set_actor_location_and_rotation(loc, rot, False, True)
            got = actor.get_actor_location()
            if math.dist((got.x, got.y, got.z), tuple(spec["loc"])) > 1.0:
                raise RuntimeError("LOOK_BENCH_MOVE_FAILED|%s (not Movable?)" % spec["label"])
            if kind in ("spot", "point"):
                comp.set_light_color(unreal.LinearColor(*spec["color"], 1.0), True)
                comp.set_attenuation_radius(float(spec["radius"]))
                comp.set_cast_shadows(bool(spec["shadows"]))
                comp.set_volumetric_scattering_intensity(float(spec["vsi"]))
                if kind == "spot":
                    comp.set_inner_cone_angle(float(spec["inner"]))
                    comp.set_outer_cone_angle(float(spec["outer"]))
                else:
                    comp.set_source_radius(float(spec["source_radius"]))
                comp.set_intensity(float(spec["cd"]))
            elif kind == "fog":
                scale = float(spec["radius_cm"]) / 500.0     # GetBaseVolumeSize() = 500 (LocalFogVolumeComponent.h:74-76)
                actor.set_actor_scale3d(unreal.Vector(scale, scale, scale * 0.6))
                comp.set_radial_fog_extinction(float(spec["density"]))
                comp.set_height_fog_extinction(float(spec["density"]))
                comp.set_height_fog_falloff(float(spec["height_falloff"]))
                comp.set_fog_phase_g(float(spec["phase_g"]))
            else:
                actor.set_actor_scale3d(unreal.Vector(*spec["scale"]))
                comp.set_material(0, make_mid(spec["material"]))
            comp.set_visibility(True, True)
            actor.set_actor_hidden_in_game(False)

        def hide_pool(self, label):
            events.append(("hide", label))
            actor = pool_actor(label)
            kind, comp = main_comp(actor)
            if kind in ("spot", "point"):
                comp.set_intensity(0.0)
            elif kind == "fog":
                comp.set_radial_fog_extinction(0.0)
                comp.set_height_fog_extinction(0.0)
            comp.set_visibility(False, True)
            actor.set_actor_hidden_in_game(True)

        def set_pool_intensity(self, label, value):
            _kind, comp = main_comp(pool_actor(label))
            comp.set_intensity(float(value))

        def material_readback(self, label):
            mid = pool_actor(label).static_mesh_component.get_material(0)
            out = {}
            for name in ("Roughness_Low", "Roughness_High", "Roughness_Add_Grunge"):
                try:
                    out[name] = float(mid.get_scalar_parameter_value(name))
                except Exception as exc:          # parameter absent on this parent
                    out[name] = "ERR " + repr(exc)
            return out

        def set_cvar(self, name, value):
            unreal.SystemLibrary.execute_console_command(world, "%s %s" % (name, value))

        def console(self, command):
            unreal.SystemLibrary.execute_console_command(world, command)

        def show_root(self):
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
            if len(roots) != 1 or not roots[0].sequence_player:
                raise RuntimeError("LOOK_BENCH_NO_SHOW_ROOT")
            return roots[0]

        def bay_pass_frame(self, passage, bay):
            """Same derivation as lighting_looks_p04_driver.build_plan, for any bay."""
            n = int(passage[1:])
            label = "Passage %d" % n
            root = self.show_root()
            segs = [s for s in root.transport.segments
                    if s.type == unreal.InfinityCueType.WING_PAIR and str(s.label) == label]
            if len(segs) != 1:
                raise RuntimeError("LOOK_BENCH_SEGMENT|" + label)
            show = unreal.load_asset(SHOW_PATH)
            rows = [r for r in show.get_editor_property("passage_settings")
                    if str(r.get_editor_property("label")) == label]
            if len(rows) != 1:
                raise RuntimeError("LOOK_BENCH_SETTINGS|" + label)
            g = lambda v: str(unreal.GuidLibrary.conv_guid_to_string(v)).replace("-", "").upper()
            cues = list(show.get_editor_property("cues"))
            first = [i for i, c in enumerate(cues) if g(c.get_editor_property("cue_guid")) ==
                     g(rows[0].get_editor_property("first_cue_guid"))]
            if len(first) != 1:
                raise RuntimeError("LOOK_BENCH_FIRST_CUE")
            frame = segs[0].start_frame.value + int(rows[0].get_editor_property("lead_in_frames").value)
            for ordinal in range(bay - 1):
                cue = cues[first[0] + ordinal]
                frame += int(cue.get_editor_property("wing_pair").get_editor_property("interval_to_next").value)
            expect = "P%02d Wing %03d" % (n, bay)
            if str(cues[first[0] + bay - 1].get_editor_property("label")) != expect:
                raise RuntimeError("LOOK_BENCH_BAY_LABEL|" + expect)
            return frame, segs[0].start_frame.value, segs[0].end_frame.value

        def transport_scrub(self, frame):
            root = self.show_root()
            root.sequence_player.pause()
            root.transport.scrub_to_master_frame(unreal.FrameNumber(int(frame)))

        def transport_play(self):
            root = self.show_root()
            root.sequence_player.set_play_rate(1.0)
            root.transport.play_forward_to_boundary()

        def transport_pause(self):
            self.show_root().sequence_player.pause()

        def transport_frame(self):
            return int(self.show_root().transport.get_current_master_frame().value)

    adapter = PieAdapter()
    adapter.events = events
    return adapter
# ---- PIE ADAPTER END ----


class CaptureMachine:
    """CAPTURE sequencing, engine-free (driven by arm()'s Slate tick; the harness drives it with
    a fake clock). Per run: POSE (read the clip-start camera -> anchor). Per state:
      [BASE_RETURN: to_base, settle, settled luma vs the first base's]  (after a non-base state)
      apply (bench strobe held dark) -> SETTLE until the luma gate says stable (or times out)
      -> frustum gate at the settled pose (LOOK_BENCH_IN_VIEW) -> release strobe -> CLIP.
    Gate failures never stop the run (restore always runs); they make it LOOK_BENCH_FAILED."""

    def __init__(self, bench, adapter, states, clip, run_dir, luma_reader=None, on_persist=None):
        self.b, self.a, self.p = bench, adapter, bench.p
        self.states = [(n, tuple(t)) for n, t in states]
        self.clip = clip
        self.run_dir = pathlib.Path(run_dir)
        self.read_luma = luma_reader or png_luma
        self.on_persist = on_persist or (lambda: None)
        self.st = {"phase": "pose", "index": 0, "clips": [], "settles": [], "base_returns": [],
                   "gate_failures": [], "base_ref": None, "anchor": None, "pose": None, "probe_n": 0,
                   "probe_timeouts": 0}

    @property
    def done(self):
        return self.st["phase"] == "done"

    def _aspect(self):
        w, h = self.p["resolution"]
        return float(w) / float(h)

    def _pose(self):
        if hasattr(self.a, "camera_pose"):
            return self.a.camera_pose(self._aspect(), self.p["fov_fallback_deg"])
        return None

    def _fail(self, why):
        self.st["gate_failures"].append(why)

    def _begin_settle(self, kind, now):
        self.a.transport_scrub(self.clip["start"])
        self.st.update(phase="settle", settle_kind=kind, t0=now, settle_ticks=0, reposed=False, samples=[],
                       pending=None, last_issue=None, deltas=[])

    def _probe(self, now, name):
        st = self.st
        pend = st["pending"]
        if pend:
            try:
                y = float(self.read_luma(pend["path"]))
            except Exception:                    # not written yet / half written: retry next tick
                if now - pend["t"] > float(self.p["probe_timeout_s"]):
                    st["probe_timeouts"] += 1
                    st["pending"] = None
                return
            st["samples"].append([round(now - st["t0"], 3), round(y, 3)])
            st["pending"] = None
            return
        if st["last_issue"] is None or now - st["last_issue"] >= float(self.p["probe_interval_s"]):
            path = self.run_dir / "_probes" / ("%02d_%s_%s_%03d.png" % (st["index"], name, st["settle_kind"],
                                                                        st["probe_n"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            st["probe_n"] += 1
            w, h = self.p["probe_resolution"]
            self.a.console('HighResShot %dx%d filename="%s"' % (w, h, path.as_posix()))
            st["pending"] = {"path": path.as_posix(), "t": now}
            st["last_issue"] = now

    def step(self, now, delta=0.0):
        st, p, a, b = self.st, self.p, self.a, self.b
        b.tick(now)
        if st["phase"] == "done":
            return
        if st["phase"] == "pose":
            a.transport_scrub(self.clip["start"])
            st.update(phase="pose_wait", t0=now, reposed=False)
            return
        if st["phase"] == "pose_wait":
            el = now - st["t0"]
            if not st["reposed"] and el >= float(p["pose_seconds"]) / 2.0:
                a.transport_scrub(self.clip["start"])
                st["reposed"] = True
            if el < float(p["pose_seconds"]):
                return
            pose = self._pose()
            if pose is None:
                raise RuntimeError("LOOK_BENCH_NO_CAMERA|no player camera manager in PIE")
            st["pose"] = pose
            st["anchor"] = b.set_anchor(pose["loc"], pose["fov_deg"], pose["aspect"])
            a.log("LOOK_BENCH_ANCHOR|run=%s|along_cm=%.0f|lateral_cm=%.0f|cam=%.0f,%.0f,%.0f|yaw=%.1f|pitch=%.1f"
                  "|fov=%.1f" % (b.run_id, st["anchor"]["along_cm"], st["anchor"]["lateral_cm"], pose["loc"][0],
                                 pose["loc"][1], pose["loc"][2], pose["rot"]["yaw"], pose["rot"]["pitch"],
                                 pose["fov_deg"]))
            st["phase"] = "start"
            return
        if st["phase"] == "start":
            if st["index"] >= len(self.states):
                st["phase"] = "done"
                return
            name, tset = self.states[st["index"]]
            a.set_cvar(STREAM_CVAR, 1)
            prev = self.states[st["index"] - 1][1] if st["index"] > 0 else ()
            if p["base_return"] and prev and tset:
                b.to_base()
                self._begin_settle("base_return", now)
            else:
                b.apply(tset, now, hold_strobe=True)
                self._begin_settle("state", now)
            return
        if st["phase"] == "settle":
            name, tset = self.states[st["index"]]
            st["settle_ticks"] += 1
            el = now - st["t0"]
            if not st["reposed"]:
                if el >= float(p["repose_seconds"]):
                    a.transport_scrub(self.clip["start"])     # re-pose: a jump's first frame is stale
                    st["reposed"] = True
                return
            st["deltas"].append(float(delta))
            self._probe(now, name)
            verdict = settle_decision(st["samples"], el, p)
            if verdict == "wait" or (verdict == "stable" and st["settle_ticks"] < int(p["settle_ticks"])):
                return
            kind = st["settle_kind"]
            luma = st["samples"][-1][1] if st["samples"] else None
            rec = {"state": name, "kind": kind, "verdict": verdict, "seconds": round(el, 3), "luma": luma,
                   "samples": st["samples"]}
            st["settles"].append(rec)
            a.log("LOOK_BENCH_SETTLE|run=%s|state=%s|kind=%s|verdict=%s|luma=%s|seconds=%.1f|probes=%d" % (
                b.run_id, name, kind, verdict, "%.1f" % luma if luma is not None else "none", el,
                len(st["samples"])))
            if verdict != "stable":
                a.log("LOOK_BENCH_SETTLE_FAILED|run=%s|state=%s|kind=%s|picture still changing after %.1f s" % (
                    b.run_id, name, kind, el))
                self._fail("settle %s/%s" % (name, kind))
            is_base = kind == "base_return" or not tset
            if is_base and luma is not None and verdict == "stable":
                ref = st["base_ref"]
                if ref is None:
                    st["base_ref"] = luma
                    a.log("LOOK_BENCH_BASE_REF|run=%s|luma=%.1f" % (b.run_id, luma))
                else:
                    ok = base_return_ok(luma, ref, p)
                    st["base_returns"].append({"before": name, "luma": luma, "ref": ref, "ok": ok})
                    a.log("LOOK_BENCH_BASE_RETURN|run=%s|before=%s|luma=%.1f|ref=%.1f|ok=%s" % (
                        b.run_id, name, luma, ref, ok))
                    if not ok:
                        self._fail("base_return before %s %.1f vs %.1f" % (name, luma, ref))
            if kind == "base_return":
                b.apply(tset, now, hold_strobe=True)
                self._begin_settle("state", now)
                return
            pose = self._pose()
            gate = view_gate(tset, b.current_specs, [pose] if pose else [], p)
            a.log("LOOK_BENCH_IN_VIEW|%s|%d|of=%d|run=%s|ok=%s%s" % (
                name, gate["n_visible"], gate["n_checkable"], b.run_id, gate["ok"],
                ("|" + ";".join(gate["fails"])) if gate["fails"] else ""))
            if not gate["ok"]:
                a.log("LOOK_BENCH_NOT_IN_VIEW|run=%s|state=%s|%s" % (b.run_id, name, ";".join(gate["fails"])))
                self._fail("view %s: %s" % (name, ";".join(gate["fails"])))
            b.release_strobe(now)
            st["current"] = {"state": name, "frames": [], "dir": (self.run_dir / name).as_posix(),
                             "frame_ms": frame_stats(st.pop("deltas", [])), "settle": rec,
                             "view_at_start": {k: v for k, v in gate.items() if k != "visible"},
                             "pose_at_start": pose, "edge_slots": len(b.record["edge_slots"]),
                             "edge_effective": bool("edge" in tset and b.record["edge_slots"])}
            pathlib.Path(st["current"]["dir"]).mkdir(parents=True, exist_ok=True)
            st["next"] = self.clip["start"]
            a.transport_play()
            st["phase"] = "clip"
            return
        if st["phase"] == "clip":
            name, tset = self.states[st["index"]]
            frame = a.transport_frame()
            cur = st["current"]
            if frame >= self.clip["end"]:
                a.transport_pause()
                poses = [f["pose"] for f in cur["frames"] if f.get("pose")]
                dev = route_deviation_deg(b._frame(), [f["camera"] for f in cur["frames"] if f.get("camera")])
                cur["route_deviation_deg"] = dev
                a.log("LOOK_BENCH_ROUTE|run=%s|state=%s|deviation_deg=%s" % (
                    b.run_id, name, "%.1f" % dev if dev is not None else "none"))
                if dev is not None and dev > float(p["route_tol_deg"]):
                    self._fail("route %s %.1f deg" % (name, dev))
                vc = view_count(b.current_specs, poses)
                cur["view_over_clip"] = {k: v for k, v in vc.items() if k != "visible"}
                a.log("LOOK_BENCH_IN_VIEW_CLIP|%s|%d|of=%d|run=%s" % (name, vc["n_visible"], vc["n_checkable"],
                                                                     b.run_id))
                st["clips"].append(st.pop("current"))
                st["index"] += 1
                st["phase"] = "start"
                self.on_persist()
                return
            if frame >= st["next"]:
                path = pathlib.Path(cur["dir"]) / ("frame_%04d.png" % len(cur["frames"]))
                w, h = p["resolution"]
                a.console('HighResShot %dx%d filename="%s"' % (w, h, path.as_posix()))
                pose = self._pose()
                cur["frames"].append({"master_frame": frame, "path": path.as_posix(),
                                      "camera": pose["loc"] if pose else None, "pose": pose,
                                      "strobe_on": bool(b.strobe and not b.strobe_hold and strobe_on(
                                          now, b.strobe_start, p["strobe_hz"], p["strobe_duty"]))})
                st["next"] = frame + self.clip["step"]


def arm(unreal, mode, toggles, states, params, prepare_path):
    if hasattr(builtins, HANDLE_NAME):
        raise RuntimeError("LOOK_BENCH_ALREADY_ARMED")
    adapter = make_pie_adapter(unreal)
    if adapter.world_kind() != "game":
        raise RuntimeError("LOOK_BENCH_NEEDS_PIE|start PIE first (PREPARE in the editor world comes before PIE)")
    prep = load_prepare_record(prepare_path)
    run_id = utc_stamp()
    run_dir = pathlib.Path(prepare_path).parent / ("capture_%s_%s" % (run_id, mode.lower()))
    run_dir.mkdir(parents=True, exist_ok=False)
    bench = LookBench(adapter, run_dir / CAPTURE_RECORD_NAME, params, run_id)
    if mode == "HOLD":
        states = [("hold", tuple(toggles))]
    bench.read_originals(states, require_pool=True, prepare_record=prep)
    p = bench.p
    states = [(n, tuple(t)) for n, t in bench.record["states"]]
    st = {"run": run_id, "mode": mode, "run_dir": run_dir.as_posix(), "phase": "start", "index": 0,
          "states": [[n, list(t)] for n, t in states], "errors": [], "ticks": 0,
          "edge_slots": len(bench.record["edge_slots"]), "prepare_record": pathlib.Path(prepare_path).as_posix()}
    setattr(builtins, STATE_NAME, st)
    holder = {"machine": None}

    def persist():
        if holder["machine"] is not None:
            st["capture"] = holder["machine"].st
            st["clips"] = holder["machine"].st["clips"]
        (run_dir / "look_bench_result.json").write_text(json.dumps(st, indent=1), encoding="utf-8")

    def finish():
        st["phase"] = "finishing"
        try:
            problems = bench.restore()
        except Exception:
            problems = ["restore raised: " + traceback.format_exc()]
        census = adapter.census()
        st["restore_problems"] = problems
        st["census_after"] = census
        if census != bench.record["census_before"]:
            problems.append("editor census changed %r -> %r" % (bench.record["census_before"], census))
        st["mid_readback"] = bench.mid_readback
        gates = list(holder["machine"].st["gate_failures"]) if holder["machine"] is not None else []
        st["gate_failures"] = gates
        st["phase"] = "done"
        st["ok"] = not problems and not st["errors"] and not gates
        persist()
        unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
        delattr(builtins, HANDLE_NAME)
        if st["ok"]:
            unreal.log("LOOK_BENCH_OK|run=%s|mode=%s|states=%d|edge_slots=%d|run_dir=%s" % (
                run_id, mode, len(states), st["edge_slots"], run_dir.as_posix()))
        else:
            unreal.log_error("LOOK_BENCH_FAILED|run=%s|problems=%r|gate_failures=%r|errors=%d" % (
                run_id, problems, gates, len(st["errors"])))
        unreal.log("%s|run=%s|pool + dirty map remain in the editor world until a Don't-Save restart" % (
            RESTART_MARKER, run_id))

    if mode == "CAPTURE":
        pass_frame, seg_start, seg_end = adapter.bay_pass_frame(p["passage"], int(p["bay"]))
        st["clip"] = clip_plan(pass_frame, p)
        if st["clip"]["start"] < seg_start or st["clip"]["end"] > seg_end:
            raise RuntimeError("LOOK_BENCH_CLIP_OUTSIDE_PASSAGE")
        holder["machine"] = CaptureMachine(bench, adapter, states, st["clip"], run_dir, on_persist=persist)
        if p["show_strobes"] == "off":
            try:
                bench.neutralise_show_strobes()  # after the record (with the strobes' originals) is on disk
            except Exception:
                problems = bench.restore()
                unreal.log_error("LOOK_BENCH_FAILED|run=%s|show strobe disable failed, restored: problems=%r|%s" % (
                    run_id, problems, traceback.format_exc()))
                raise

    def tick(_delta):
        if st.get("inside") or st["phase"] in ("done", "finishing"):
            return
        st["inside"] = True
        try:
            now = time.monotonic()
            if adapter.world_kind() != "game":
                raise RuntimeError("LOOK_BENCH_PIE_ENDED")
            st["ticks"] += 1
            if mode == "HOLD":
                bench.tick(now)
                if st["phase"] == "start":
                    bench.apply(toggles, now)
                    st["phase"], st["until"] = "hold", now + float(p["hold_seconds"])
                elif now >= st["until"]:
                    finish()
                return
            holder["machine"].step(now, float(_delta))
            if holder["machine"].done:
                finish()
        except Exception:
            st["errors"].append(traceback.format_exc())
            try:
                finish()
            except Exception:
                st["errors"].append(traceback.format_exc())
                persist()
                if hasattr(builtins, HANDLE_NAME):
                    unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
                    delattr(builtins, HANDLE_NAME)
        finally:
            st["inside"] = False

    persist()
    setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))
    unreal.log("LOOK_BENCH_ARMED|run=%s|mode=%s|run_dir=%s" % (run_id, mode, run_dir.as_posix()))
    return run_dir


def main():
    import unreal
    g = globals()
    mode = g.get("BENCH_MODE", "PROBE")
    params = dict(g.get("BENCH_PARAMS", {}))
    if mode == "PREPARE":
        adapter = make_editor_adapter(unreal)
        if adapter.world_kind() != "editor":
            raise RuntimeError("LOOK_BENCH_PREPARE_NEEDS_EDITOR|world=%s" % adapter.world_kind())
        run_id = utc_stamp()
        run_dir = BENCH_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        PrepareBench(adapter, run_dir / PREPARE_RECORD_NAME, g.get("BENCH_BAYS"), params, run_id).run()
        return
    if mode == "CLEANUP":
        cleanup(make_editor_adapter(unreal), find_prepare_record(BENCH_DIR, g.get("BENCH_PREPARE_RECORD")))
        return
    if mode == "RESTORE":
        adapter = make_pie_adapter(unreal)
        if adapter.world_kind() != "game":
            raise RuntimeError("LOOK_BENCH_NEEDS_PIE|RESTORE works on the PIE copies")
        explicit = g.get("BENCH_RECORD")
        if explicit:
            records = [explicit] if isinstance(explicit, (str, pathlib.Path)) else list(explicit)
        else:
            prep = find_prepare_record(BENCH_DIR, g.get("BENCH_PREPARE_RECORD"))
            records = sorted(prep.parent.glob("capture_*/" + CAPTURE_RECORD_NAME))
        problems = restore_all(adapter, records, unreal.log)
        if problems:
            unreal.log_error("LOOK_BENCH_RESTORE_FAILED|%r" % problems)
        else:
            unreal.log("LOOK_BENCH_RESTORE_OK|records=%d" % len(records))
        unreal.log("%s|pool + dirty map remain in the editor world; end PIE, then restart the editor choosing "
                   "Don't Save" % RESTART_MARKER)
        return
    if mode == "PROBE":
        adapter = make_pie_adapter(unreal)
        if adapter.world_kind() != "game":
            raise RuntimeError("LOOK_BENCH_NEEDS_PIE")
        run_id = utc_stamp()
        out = BASE / ("look_bench_probe_%s.json" % run_id)
        bench = LookBench(adapter, out, params, run_id)
        bench.read_originals(None, require_pool=False)     # reads + writes the file; changes nothing
        unreal.log("LOOK_BENCH_PROBE_OK|lights=%d|edge_slots=%d|pool_in_pie=%d|path=%s" % (
            len(bench.record["lights"]), len(bench.record["edge_slots"]), len(adapter.pool_labels()),
            out.as_posix()))
        return
    if mode not in ("CAPTURE", "HOLD"):
        raise RuntimeError("LOOK_BENCH_BAD_MODE|" + str(mode))
    toggles = tuple(g.get("BENCH_TOGGLES", ("shadows", "haze", "rake", "floor_wet", "strobe", "edge")))
    states = g.get("BENCH_STATES")
    arm(unreal, mode, toggles, [(n, tuple(t)) for n, t in states] if states else None, params,
        find_prepare_record(BENCH_DIR, g.get("BENCH_PREPARE_RECORD")))


if __name__ == "__main__" or "BENCH_MODE" in globals():
    main()
