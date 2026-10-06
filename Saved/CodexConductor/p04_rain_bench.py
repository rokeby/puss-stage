"""P04 RAIN BENCH: a NON-SAVING rain prototype over Passage 4, shot as PIE stills (Gary, 6 Oct ~00:45: P04
"already feels like a rainy moody passage" with its stormy strobe opening; rain tonight, bench only, stills,
nothing saved into the show).

WHAT IT MAKES
  A Niagara rain made by DUPLICATING Niagara's own lightweight (stateless) template
  /Niagara/DefaultAssets/Templates/Systems/FountainLightweight into CREATE-ONLY bench assets under
  /Game/InfinityStage/Bench/ (NS_ZZ_P04Rain, optional NS_ZZ_P04RainSplash, optional M_ZZ_P04RainStreak), retuned
  by reflection: box spawn shape at the rain top, constant downward velocity, vertical CUSTOM-aligned streak
  sprites (width x length), lifetime = fall height / speed, spawn rate = density x tile area.
  Nothing in the project's Content is a rain system: a binary scan of every Content/**/*.uasset for the class string
  "NiagaraSystem" (6 Oct) found only KK_S2_Shrine/Falling_Leaves (NS_Falling_Leaves + BP_Falling_Leaves) [measured].

WHY NO ZZ_ ACTOR (the deviation from the usual bench pool), and where the rain lives
  - UE 5.8 Python has NO route that spawns an ACTOR into a running PIE world (look_bench.py:4-9, measured by its
    spawn-API probe on 5 Oct: begin_deferred_actor_spawn_from_class does not exist; only the editor-world
    spawners exist). An editor-world ZZ_ pool dirties the map and needs a Don't-Save restart (look_bench /
    p02_fog_bench), which breaks "the level must end clean".
  - UNiagaraFunctionLibrary::SpawnSystemAtLocation IS BlueprintCallable with a WorldContext
    (NiagaraFunctionLibrary.h:92-93) [declaration-proven]. Given the PIE world it spawns an actor-less
    NiagaraComponent INTO PIE. Nothing in the editor world is touched, and the PIE world (with the components) is
    destroyed when PIE ends, so PIE end is a backstop for TEARDOWN_PIE [inferred: standard PIE teardown; the
    census in every step measures the editor side].
  - The bench identifies its components by ASSET IDENTITY (their system is a bench-created asset no one else uses)
    plus the object paths written to the setup record, never by a module-global reference.

WHY IT IS GATED BY A PROBE
  The bee-swarm stream found the CLASSIC Niagara graph unauthorable from Python (Saved/CodexBeeSwarm/
  bee_swarm_niagara_verify.py:4-8: NiagaraSystemFactoryNew.h:23-24, NiagaraSystem.h:975-976). Stateless emitters
  are different: UNiagaraStatelessEmitter keeps SpawnInfos / Modules / RendererProperties / FixedBounds as
  EditAnywhere UPROPERTYs (Internal/Stateless/NiagaraStatelessEmitter.h:207-223) and every module setting is an
  EditAnywhere UPROPERTY (e.g. NiagaraStatelessModule_ShapeLocation.h:39-46, _AddVelocity.h:35-40,
  _InitializeParticle.h:21-33, _SpriteFacingAndAlignment.h:17-26) [declaration-proven]. BUT the distribution
  structs (FNiagaraDistributionRangeFloat etc., NiagaraStatelessDistribution.h:213-298) and
  FNiagaraStatelessSpawnInfo (NiagaraStatelessSpawnInfo.h:17) are USTRUCT() WITHOUT BlueprintType, and whether UE
  Python exposes such properties is UNCLEAR (PyGenUtil.h:1118-1133 declares ShouldExportStruct/Property; the .cpp
  is not in this install). It is also UNCLEAR how emitters are reached from the system (EmitterHandles is a bare
  UPROPERTY(), per bee swarm); this bench finds them with unreal.ObjectIterator by outer path. So:
    PROBE (read only) measures every path the retune needs and logs authorable=yes|no. CREATE refuses unless
    the newest probe said yes. CREATE asserts a read-back after EVERY set (memory: setters lie) and rolls back
    (deletes) what it created on the first mismatch. "Python cannot author this" is then a MEASURED answer.

STROBE FLASH STILL
  AInfinityStageStrobeLight takes its phase from the Master clock in game worlds
  (InfinityStageStrobeLight.cpp:85-121; LevelAt at .cpp:12-37) [source-proven], so a PAUSED Master frame holds a
  fixed strobe level. The bench reads the live strobe settings in PIE, picks a Master frame in the middle of a
  flash with the camera flash_lead_cm short of the strobe, and a DARK partner frame (level 0) at the same place,
  and converts both to Passage fractions for passage_stills.py. level_at() here is a line-for-line copy of LevelAt.

MODES (BENCH_MODE via p04_rain_bench_mode.json + p04_rain_bench_run.py; VERIFY also runs offline:
`python Saved/CodexConductor/p04_rain_bench.py verify`)
  PROBE         editor, PIE off. Read only. Loads the template, reports reachability. -> PROBE_OK
  CREATE        editor, PIE off, census clean. Writes the create record (planned assets) BEFORE the first create,
                duplicates the template, retunes with read-backs, optional streak material + splash system.
                Leaves exactly its own new packages dirty (never saved). -> CREATE_OK
  PIE_BEGIN     editor, PIE off. Allows ONLY the bench's own dirty content packages and no dirty map, then
                requests PIE (the bench's variant of conductor_pie_begin.py). -> PIE_BEGIN_REQUESTED
  SETUP         PIE. Reads the segment, tick resolution, strobes; plans fractions + tiles; WRITES the setup record
                (plan + 'spawned': []) BEFORE the first spawn; spawns one component per tile into PIE; records
                every component path; census before == after. -> SETUP_OK
  STILLS        PIE. Rain visible; arms passage_stills.py (P04, the planned fractions, label 'rain').
                Wait for PASSAGE_STILLS_OK|run=PSTILLS-P04-...-rain. -> STILLS_ARMED
  STILLS_NORAIN PIE. Hides the rain components (runtime set_visibility, recorded) and arms the same fractions with
                label 'norain'. -> STILLS_ARMED (a later STILLS or TEARDOWN_PIE restores/destroys)
  VERIFY        anywhere (offline preferred). Both manifests passed; camera poses inside the planned route band;
                tile coverage of each ACTUAL frustum; rain vs no-rain pixel difference; flash vs dark luma.
                -> VERIFY_OK
  TEARDOWN_PIE  PIE. Deactivates + destroys every bench component (by record path and by asset sweep);
                verifies none is left valid. -> TEARDOWN_PIE_OK. Then the conductor runs conductor_pie_end.py.
  TEARDOWN      editor, PIE off. Sweeps for bench components, deletes ONLY the assets the create record says the
                bench created (bench folder, ZZ_ names), verifies they are gone and the census is
                {content: [], maps: []}. -> TEARDOWN_OK, else NEEDS_DONT_SAVE_RESTART.

Markers: P04_RAIN_BENCH_<STEP>_OK|run=<bench run>|..., P04_RAIN_BENCH_FAILED|run=..|step=..|reason=..,
P04_RAIN_BENCH_NEEDS_DONT_SAVE_RESTART|run=... Every record is written fsynced + re-read (passage_stills
write_verified) and its path is logged BEFORE the change it describes. No save call anywhere (harness scan); no
actor spawn API anywhere (harness scan); the bench never ends PIE and never reloads a level; Unreal objects live
only inside functions (memory: UE wrappers in module globals crashed the editor).
"""
from __future__ import annotations

import datetime
import json
import math
import os
import pathlib
import re
import struct
import sys
import time
import traceback
import zlib

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
import passage_stills as ps  # noqa: E402  (pure helpers + stills arm; no unreal import at module level)

OUT = BASE / "P04RainBench"
PROBE_RECORD = OUT / "p04_rain_bench_probe.json"
CREATE_RECORD = OUT / "p04_rain_bench_create.json"
SETUP_RECORD = OUT / "p04_rain_bench_setup.json"
VERIFY_RECORD = OUT / "p04_rain_bench_verify.json"
TEARDOWN_RECORD = OUT / "p04_rain_bench_teardown.json"
MARK = "P04_RAIN_BENCH"
BENCH_FOLDER = "/Game/InfinityStage/Bench"
NS_RAIN = BENCH_FOLDER + "/NS_ZZ_P04Rain"
NS_SPLASH = BENCH_FOLDER + "/NS_ZZ_P04RainSplash"
M_STREAK = BENCH_FOLDER + "/M_ZZ_P04RainStreak"
BENCH_ASSETS = (NS_RAIN, NS_SPLASH, M_STREAK)
TEMPLATE = "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight"
STATELESS_EMITTER_CLASS = "NiagaraStatelessEmitter"
SPRITE_RENDERER_CLASS = "NiagaraSpriteRendererProperties"
MOD = "NiagaraStatelessModule_"
MODES = ("PROBE", "CREATE", "PIE_BEGIN", "SETUP", "STILLS", "STILLS_NORAIN", "VERIFY", "TEARDOWN_PIE", "TEARDOWN")

DEFAULTS = {
    "passage": "P04",
    # Route model: the Passage camera travels +X at constant y/z, x linear in the Passage fraction.
    # [measured] PassageStills/PSTILLS-P04-20261005-125030-rigB: f 0.1 -> x 1066.8, 0.9 -> 9601.6 (slope 10668.5,
    # intercept ~0), y 240000, z 180, yaw 0, fov 37.497. SETUP re-reads nothing of this; VERIFY checks every
    # ACTUAL still pose against it (route_tol_cm) and fails if the camera left the band.
    "route": {"x0": 0.0, "x1": 10668.5, "y": 240000.0, "z": 180.0},
    "route_tol_cm": 150.0,
    "fov_deg": 37.497,
    "aspect": 16.0 / 9.0,
    "base_fractions": (0.1, 0.35, 0.6, 0.85),
    # Placement: one rain tile run covers [cam_x + near, cam_x + far] for every still ("a few bays ahead": P04 has
    # 21 bays over ~10.7 m... ~510 cm pitch [inferred from lighting_scores_record_P04.json plan.bay_count=21 and
    # the route length], so 3600 cm is ~7 bays).
    "near_cm": 150.0,
    "far_cm": 3600.0,
    "half_width_cm": 900.0,          # rain either side of the route centre line [inferred: wings mask beyond]
    "merge_gap_cm": 600.0,
    "tile_len_cm": 1800.0,
    "x_clip": (-600.0, 12500.0),     # never rain far past the Passage ends
    "floor_z": 0.0,                  # [inferred] camera z 180 is eye height over a z=0 floor (strobe "just above
                                     # the floor" at z 60, place_default_strobe_p04_record.json)
    "rain_top_cm": 950.0,            # spawn plane height over the floor; must clear the frame top at far_cm
    "spawn_thickness_cm": 20.0,
    "fall_speed_cms": 900.0,         # [inferred] terminal speed of large drops, ~9 m/s
    "streak_width_cm": 0.8,
    "streak_length_cm": 55.0,
    "color": (0.62, 0.68, 0.75, 0.30),
    "density_per_m2_s": 40.0,       # ~4 streaks per m3 live; 7 tiles over P04 = ~96k live [inferred look]
    "max_live_particles": 200000,
    "min_view_coverage": 0.6,
    "coverage_depths": 8,
    "coverage_laterals": 9,
    "material": "bench_lit",        # "bench_lit" = M_ZZ_P04RainStreak (translucent, lit per-vertex volumetric) |
                                     # "template" = keep the template sprite material
    "splash": False,                 # optional cheap floor splash: a second system, tiny short sprites at the floor
    "splash_density_per_m2_s": 60.0,
    "splash_life_s": 0.12,
    "splash_size_cm": 3.0,
    "splash_up_cms": 80.0,
    "splash_color": (0.7, 0.75, 0.8, 0.35),
    # Strobe flash still
    "flash": True,
    "flash_lead_cm": 1200.0,         # camera this far short of the strobe
    "flash_point": 0.5,              # where inside the flash window (0 = its first tick, 1 = its last)
    "dark_offset_periods": 0.5,
    "strobe_route_band_cm": 2500.0,
    "fraction_range": (0.02, 0.98),
    # Stills (passage through to passage_stills.py; the show's exposure, no override)
    "stills_params": {},
    "require_norain": True,
    "min_rain_diff": 1.0,            # mean |rain - norain| per channel, 0..255
    "min_flash_delta": 2.0,          # luma(flash) - luma(dark)
    "delete_assets": True,
}

DISABLE_MODULES = ("GravityForce", "CurlNoiseForce", "Drag", "AccelerationForce", "ScaleSpriteSize",
                   "ScaleSpriteSizeBySpeed", "SpriteRotationRate", "RotateAroundPoint", "CameraOffset",
                   "SubUVAnimation", "ScaleColor", "DynamicMaterialParameters")
MUST_DISABLE = ("GravityForce", "AccelerationForce", "CurlNoiseForce", "Drag")


class RainRefused(RuntimeError):
    def __init__(self, reason, detail="", run="?", step="?"):
        self.reason, self.detail, self.step = reason, str(detail), step
        super().__init__("%s_FAILED|run=%s|step=%s|reason=%s%s" % (MARK, run, step, reason,
                                                                    ("|" + self.detail) if detail else ""))


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def params_of(overrides=None):
    p = json.loads(json.dumps(DEFAULTS))
    for k, v in (overrides or {}).items():
        if k not in DEFAULTS:
            raise RainRefused("bad_param", k)
        p[k] = v
    return p


def write_record(path, data, log=print):
    """passage_stills.write_verified (fsync-free but re-read) + log the path. Called BEFORE the change described."""
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    ps.write_verified(path, data)
    log("%s_RECORD|path=%s" % (MARK, pathlib.Path(path).as_posix()))
    return path


def read_record(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# pure planning maths (tested offline by test_p04_rain_bench.py)
# --------------------------------------------------------------------------

def route_x(fraction, route):
    return float(route["x0"]) + float(fraction) * (float(route["x1"]) - float(route["x0"]))


def route_fraction(x, route):
    span = float(route["x1"]) - float(route["x0"])
    if span <= 0:
        raise RainRefused("bad_route", repr(route))
    return (float(x) - float(route["x0"])) / span


def merge_intervals(intervals, gap):
    out = []
    for a, b in sorted((float(a), float(b)) for a, b in intervals if b > a):
        if out and a - out[-1][1] <= float(gap):
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(x) for x in out]


def plan_tiles(fractions, p):
    """Contiguous fixed-size tiles covering [cam_x + near, cam_x + far] for every still, clipped to x_clip."""
    route, L = p["route"], float(p["tile_len_cm"])
    lo, hi = float(p["x_clip"][0]), float(p["x_clip"][1])
    if L <= 0 or p["near_cm"] < 0 or p["far_cm"] <= p["near_cm"]:
        raise RainRefused("bad_tile_params", "L=%r near=%r far=%r" % (L, p["near_cm"], p["far_cm"]))
    want = []
    for f in fractions:
        cx = route_x(f, route)
        a, b = max(lo, cx + float(p["near_cm"])), min(hi, cx + float(p["far_cm"]))
        if b > a:
            want.append((a, b))
    runs = merge_intervals(want, p["merge_gap_cm"])
    tiles = []
    for a, b in runs:
        n = int(math.ceil((b - a) / L - 1e-9))
        start = a
        if start + n * L > hi:              # shift the run back so it ends at the clip
            start = max(lo, hi - n * L)
        for i in range(n):
            cx = start + (i + 0.5) * L
            tiles.append({"center": [cx, float(route["y"]), float(p["floor_z"]) + float(p["rain_top_cm"])],
                          "size": [L, 2.0 * float(p["half_width_cm"]), float(p["spawn_thickness_cm"])],
                          "x_range": [cx - L / 2.0, cx + L / 2.0]})
    return {"wanted": [list(w) for w in want], "runs": [list(r) for r in runs], "tiles": tiles}


def covers(tiles, a, b, tol=1e-6):
    """True when the union of tile x-ranges contains [a, b]."""
    spans = merge_intervals([t["x_range"] for t in tiles], 0.0)
    return any(s[0] <= a + tol and s[1] >= b - tol for s in spans)


def tiles_overlap(tiles):
    xs = sorted(tuple(t["x_range"]) for t in tiles)
    return any(xs[i + 1][0] < xs[i][1] - 1e-6 for i in range(len(xs) - 1))


def rain_physics(p):
    v = float(p["fall_speed_cms"])
    if v <= 0:
        raise RainRefused("bad_speed", v)
    life = float(p["rain_top_cm"]) / v       # spawned at the top plane, dies at the floor
    L, W = float(p["tile_len_cm"]), 2.0 * float(p["half_width_cm"])
    rate = float(p["density_per_m2_s"]) * (L / 100.0) * (W / 100.0)
    return {"lifetime_s": life, "rate_per_tile": rate, "live_per_tile": rate * life}


def vertical_half_tan(p):
    return math.tan(math.radians(float(p["fov_deg"]) / 2.0)) / float(p["aspect"])


def frame_top_z(p, depth):
    return float(p["route"]["z"]) + depth * vertical_half_tan(p)


def view_coverage(pose, tiles, p):
    """Fraction of sample points on horizontal frustum slices (depths near..far, laterals across the frame width but
    inside the wing line) that fall in a tile footprint. pose = {"loc": [x,y,z], "rot": {"yaw": deg}, "fov_deg"}."""
    x, y = float(pose["loc"][0]), float(pose["loc"][1])
    yaw = math.radians(float(pose["rot"]["yaw"]))
    fwd, right = (math.cos(yaw), math.sin(yaw)), (-math.sin(yaw), math.cos(yaw))
    th = math.tan(math.radians(float(pose.get("fov_deg") or p["fov_deg"]) / 2.0))
    nd, nl = int(p["coverage_depths"]), int(p["coverage_laterals"])
    near, far = max(float(p["near_cm"]), 300.0), float(p["far_cm"])
    inside = total = 0
    for i in range(nd):
        d = near + (far - near) * (i + 0.5) / nd
        half = min(d * th, float(p["half_width_cm"]))
        for j in range(nl):
            l = -half + 2.0 * half * (j + 0.5) / nl
            px, py = x + d * fwd[0] + l * right[0], y + d * fwd[1] + l * right[1]
            total += 1
            for t in tiles:
                cx, cy = t["center"][0], t["center"][1]
                if abs(px - cx) <= t["size"][0] / 2.0 + 1e-6 and abs(py - cy) <= t["size"][1] / 2.0 + 1e-6:
                    inside += 1
                    break
    return inside / float(total) if total else 0.0


def check_plan(plan, fractions, p):
    """Raises on any placement / budget fault. Returns the summary dict."""
    phys = rain_physics(p)
    if not plan["tiles"]:
        raise RainRefused("no_tiles")
    for a, b in plan["wanted"]:
        if not covers(plan["tiles"], a, b):
            raise RainRefused("tiles_miss_interval", "%.0f..%.0f" % (a, b))
    if tiles_overlap(plan["tiles"]):
        raise RainRefused("tiles_overlap")
    lo, hi = p["x_clip"]
    for t in plan["tiles"]:
        if t["x_range"][0] < lo - 1e-6 or t["x_range"][1] > hi + 1e-6:
            raise RainRefused("tile_outside_clip", t["x_range"])
    top_needed = frame_top_z(p, float(p["far_cm"])) + float(p["streak_length_cm"])
    top = float(p["floor_z"]) + float(p["rain_top_cm"])
    if top < top_needed:
        raise RainRefused("rain_top_below_frame_top", "%.0f < %.0f" % (top, top_needed))
    live = phys["live_per_tile"] * len(plan["tiles"])
    if p.get("splash"):
        live += splash_physics(p)["live_per_tile"] * len(plan["tiles"])
    if live > float(p["max_live_particles"]):
        raise RainRefused("particle_budget", "%d > %d" % (live, p["max_live_particles"]))
    cov = []
    for f in fractions:
        pose = {"loc": [route_x(f, p["route"]), p["route"]["y"], p["route"]["z"]], "rot": {"yaw": 0.0},
                "fov_deg": p["fov_deg"]}
        c = view_coverage(pose, plan["tiles"], p)
        cov.append(round(c, 3))
        if c < float(p["min_view_coverage"]):
            raise RainRefused("view_coverage", "f=%.3f coverage=%.2f" % (f, c))
    return {"live_particles": int(live), "tiles": len(plan["tiles"]), "coverage": cov, "physics": phys,
            "rain_top_z": top, "frame_top_needed_z": top_needed}


def splash_physics(p):
    L, W = float(p["tile_len_cm"]), 2.0 * float(p["half_width_cm"])
    rate = float(p["splash_density_per_m2_s"]) * (L / 100.0) * (W / 100.0)
    return {"lifetime_s": float(p["splash_life_s"]), "rate_per_tile": rate,
            "live_per_tile": rate * float(p["splash_life_s"])}


# ---- strobe (copy of InfinityStageStrobe::LevelAt, InfinityStageStrobeLight.cpp:12-37)

def level_at(show_seconds, period, flash, decay, phase):
    if period <= 0.0:
        return 0.0
    cycle = math.fmod(show_seconds / period + phase, 1.0)
    if cycle < 0.0:
        cycle += 1.0
    local = cycle * period
    fl = max(0.0, flash)
    if local < fl:
        return 1.0
    after = local - fl
    if decay <= 0.0 or after >= decay:
        return 0.0
    tau = decay / 4.6
    return math.exp(-after / tau)


def strobe_level_at_frame(frame, tps, s):
    return level_at(float(frame) / float(tps), float(s["period_seconds"]), float(s["flash_seconds"]),
                    float(s["decay_seconds"]), float(s["phase_cycles"]))


def pick_strobe(strobes, segment_guid, p):
    """Enabled strobes active in the Passage (empty filter = everywhere), on the route band, lowest x first."""
    route = p["route"]
    rows = []
    for s in strobes:
        if not s.get("enabled"):
            continue
        guids = [str(g).upper() for g in (s.get("active_segment_guids") or [])]
        if guids and str(segment_guid).upper() not in guids:
            continue
        x, y = float(s["location"][0]), float(s["location"][1])
        if not (route["x0"] <= x <= route["x1"]) or abs(y - route["y"]) > float(p["strobe_route_band_cm"]):
            continue
        if float(s["period_seconds"]) <= 0 or float(s["flash_seconds"]) <= 0:
            continue
        rows.append(s)
    return sorted(rows, key=lambda s: float(s["location"][0]))[0] if rows else None


def flash_frames(segment, tps, strobe, p):
    """(flash_frame, dark_frame) Master frames inside the segment: flash mid-window with the camera flash_lead_cm
    short of the strobe; dark = level 0 at about +dark_offset_periods."""
    start, end = int(segment[0]), int(segment[1])
    guard = ps.END_GUARD_TICKS
    period, flash = float(strobe["period_seconds"]), float(strobe["flash_seconds"])
    phase = float(strobe["phase_cycles"])
    f_lo, f_hi = p["fraction_range"]
    f_t = min(max(route_fraction(float(strobe["location"][0]) - float(p["flash_lead_cm"]), p["route"]), f_lo), f_hi)
    t_target = (start + f_t * (end - start)) / float(tps)
    within = float(p["flash_point"]) * flash / period
    k0 = round(t_target / period + phase - within)
    for dk in (0, 1, -1, 2, -2):
        t = (k0 + dk - phase + within) * period
        fr = int(round(t * tps))
        if start <= fr <= end - guard and strobe_level_at_frame(fr, tps, strobe) >= 1.0:
            break
    else:
        raise RainRefused("no_flash_frame", "segment %d..%d" % (start, end))
    for step in range(0, 20):
        dark = fr + int(round((float(p["dark_offset_periods"]) + 0.05 * step) * period * tps))
        if dark > end - guard:
            dark = fr - int(round((float(p["dark_offset_periods"]) + 0.05 * step) * period * tps))
        if start <= dark <= end - guard and strobe_level_at_frame(dark, tps, strobe) < 0.01:
            return fr, dark
    raise RainRefused("no_dark_frame", "strobe never dark: decay %.3f period %.3f" % (
        float(strobe["decay_seconds"]), period))


def frame_to_fraction(segment, frame):
    start, end = int(segment[0]), int(segment[1])
    return (int(frame) - start) / float(end - start)


def plan_fractions(segment, tps, strobe, p):
    """Base fractions + optional flash/dark pair. Every fraction round-trips through passage_stills."""
    if int(tps) != ps.TICKS_PER_SECOND:
        raise RainRefused("tick_resolution", "show %s, passage_stills assumes %d" % (tps, ps.TICKS_PER_SECOND))
    rows = [{"kind": "base", "fraction": float(f)} for f in p["base_fractions"]]
    flash = None
    if p.get("flash") and strobe is not None:
        fr, dark = flash_frames(segment, tps, strobe, p)
        flash = {"flash_frame": fr, "dark_frame": dark,
                 "flash_level": strobe_level_at_frame(fr, tps, strobe),
                 "dark_level": strobe_level_at_frame(dark, tps, strobe), "strobe": strobe}
        rows.append({"kind": "flash", "fraction": frame_to_fraction(segment, fr)})
        rows.append({"kind": "dark", "fraction": frame_to_fraction(segment, dark)})
    fr_list = ps.validate_fractions([r["fraction"] for r in rows])
    stills = ps.plan_stills(segment[0], segment[1], fr_list, OUT / "_dry")
    for r, s in zip(rows, stills):
        r["target_frame"] = s["target_frame"]
        if flash and r["kind"] in ("flash", "dark"):
            want = flash["flash_frame"] if r["kind"] == "flash" else flash["dark_frame"]
            lvl = strobe_level_at_frame(s["target_frame"], tps, strobe)
            if abs(s["target_frame"] - want) > 1 or (r["kind"] == "flash" and lvl < 1.0) or \
                    (r["kind"] == "dark" and lvl >= 0.01):
                raise RainRefused("flash_roundtrip", "%s want %d got %d level %.3f" % (
                    r["kind"], want, s["target_frame"], lvl))
            r["strobe_level"] = lvl
    return rows, flash


# ---- retune spec (what CREATE writes into the duplicated stateless emitter)

def rain_spec(p, material_path=None):
    phys = rain_physics(p)
    L, W, T = float(p["tile_len_cm"]), 2.0 * float(p["half_width_cm"]), float(p["spawn_thickness_cm"])
    top = float(p["rain_top_cm"])
    return {
        "spawn_rate": phys["rate_per_tile"],
        "fixed_bounds": {"min": [-L / 2 - 100.0, -W / 2 - 100.0, -top - 200.0], "max": [L / 2 + 100.0, W / 2 + 100.0, 100.0]},
        "modules": {
            "ShapeLocation": {"enums": {"shape_primitive": "BOX"}, "bools": {"box_surface_only": False},
                              "dists": {"box_size": ("NON_UNIFORM_CONSTANT", [L, W, T])}},
            "AddVelocity": {"enums": {"velocity_type": "LINEAR"},
                            "dists": {"linear_velocity_distribution": ("NON_UNIFORM_CONSTANT",
                                                                       [0.0, 0.0, -float(p["fall_speed_cms"])]),
                                      "linear_velocity_scale": ("UNIFORM_CONSTANT", [1.0])}},
            "InitializeParticle": {"dists": {"lifetime_distribution": ("UNIFORM_CONSTANT", [phys["lifetime_s"]]),
                                             "sprite_size_distribution": ("NON_UNIFORM_CONSTANT",
                                                                          [float(p["streak_width_cm"]),
                                                                           float(p["streak_length_cm"])]),
                                             "sprite_rotation_distribution": ("UNIFORM_CONSTANT", [0.0])},
                                   "colors": {"color_distribution": [float(c) for c in p["color"]]}},
            "SpriteFacingAndAlignment": {"bools": {"sprite_alignment_enabled": True, "sprite_facing_enabled": False},
                                         "dists": {"sprite_alignment": ("NON_UNIFORM_CONSTANT", [0.0, 0.0, 1.0])}},
            "SolveVelocitiesAndForces": {},
        },
        "disable": list(DISABLE_MODULES),
        "renderer": {"enums": {"alignment": "CUSTOM_ALIGNMENT", "facing_mode": "FACE_CAMERA"},
                     "material": material_path},
    }


def splash_spec(p, material_path=None):
    phys = splash_physics(p)
    L, W = float(p["tile_len_cm"]), 2.0 * float(p["half_width_cm"])
    s = float(p["splash_size_cm"])
    return {
        "spawn_rate": phys["rate_per_tile"],
        "fixed_bounds": {"min": [-L / 2 - 50.0, -W / 2 - 50.0, -20.0], "max": [L / 2 + 50.0, W / 2 + 50.0, 60.0]},
        "modules": {
            "ShapeLocation": {"enums": {"shape_primitive": "BOX"}, "bools": {"box_surface_only": False},
                              "dists": {"box_size": ("NON_UNIFORM_CONSTANT", [L, W, 2.0])}},
            "AddVelocity": {"enums": {"velocity_type": "LINEAR"},
                            "dists": {"linear_velocity_distribution": ("NON_UNIFORM_CONSTANT",
                                                                       [0.0, 0.0, float(p["splash_up_cms"])]),
                                      "linear_velocity_scale": ("UNIFORM_CONSTANT", [1.0])}},
            "InitializeParticle": {"dists": {"lifetime_distribution": ("UNIFORM_CONSTANT", [phys["lifetime_s"]]),
                                             "sprite_size_distribution": ("NON_UNIFORM_CONSTANT", [s, s * 0.6]),
                                             "sprite_rotation_distribution": ("UNIFORM_CONSTANT", [0.0])},
                                   "colors": {"color_distribution": [float(c) for c in p["splash_color"]]}},
            "SolveVelocitiesAndForces": {},
        },
        "disable": list(DISABLE_MODULES) + ["SpriteFacingAndAlignment"],
        "renderer": {"enums": {"alignment": "UNALIGNED", "facing_mode": "FACE_CAMERA"}, "material": material_path},
    }


def channels_for(mode, values):
    """Editor-side channel data consistent with a CONSTANT mode: UNIFORM -> [v], NON_UNIFORM -> the values.
    [inferred layout: FNiagaraDistributionBase::ChannelConstantsAndRanges, NiagaraStatelessDistribution.h:128;
    CREATE reads Min/Max back after the set, so a wrong guess fails loudly instead of rendering wrong]."""
    vals = [float(v) for v in values]
    if mode == "UNIFORM_CONSTANT":
        if len(vals) != 1:
            raise RainRefused("uniform_needs_one_value", vals)
        return vals
    if mode == "NON_UNIFORM_CONSTANT":
        return vals
    raise RainRefused("mode_not_constant", mode)


def probe_paths(spec):
    """Every (owner, property) the retune touches: the PROBE must be able to READ each one."""
    rows = [("emitter", "spawn_infos"), ("emitter", "modules"), ("emitter", "renderer_properties"),
            ("emitter", "fixed_bounds")]
    for m, body in spec["modules"].items():
        rows.append((MOD + m, "module_enabled"))
        for k in list(body.get("enums", {})) + list(body.get("bools", {})) + list(body.get("dists", {})) + \
                list(body.get("colors", {})):
            rows.append((MOD + m, k))
    for m in spec["disable"]:
        rows.append((MOD + m, "module_enabled?"))     # '?' = optional (absent module is fine)
    rows.append(("renderer", "alignment"))
    rows.append(("renderer", "facing_mode"))
    rows.append(("renderer", "material"))
    return rows


# ---- retune engine (duck-typed: the harness drives it with fake objects; CREATE with Unreal wrappers)

def _close(a, b, tol=1e-3):
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


VEC_FIELDS = {1: None, 2: ("x", "y"), 3: ("x", "y", "z"), 4: ("r", "g", "b", "a")}


def _vec_read(v, n):
    if n == 1:
        return [float(v)]
    return [float(getattr(v, f)) for f in VEC_FIELDS[n]]


def _vec_write(cur, values):
    n = len(values)
    if n == 1:
        return float(values[0])
    for f, val in zip(VEC_FIELDS[n], values):
        setattr(cur, f, float(val))
    return cur


def _enum_value(cur, name):
    etype = type(cur)
    if not hasattr(etype, name):
        raise RainRefused("enum_value_missing", "%s.%s" % (etype.__name__, name))
    return getattr(etype, name)


class Retuner:
    """Applies a spec to ONE stateless emitter with a read-back after every set. 'log' collects rows for the
    create record; any mismatch raises RainRefused('readback_mismatch')."""

    def __init__(self, emitter, kit, log):
        self.em, self.kit, self.log = emitter, kit, log

    def _set(self, obj, name, value, check):
        obj.set_editor_property(name, value)
        got = obj.get_editor_property(name)
        ok = check(got)
        self.log.append({"obj": self.kit.name(obj), "prop": name, "ok": bool(ok), "got": self.kit.show(got)})
        if not ok:
            raise RainRefused("readback_mismatch", "%s.%s -> %s" % (self.kit.name(obj), name, self.kit.show(got)))
        return got

    def modules(self):
        return {self.kit.class_name(m): m for m in list(self.em.get_editor_property("modules")) if m is not None}

    def set_enum(self, obj, name, label):
        val = _enum_value(obj.get_editor_property(name), label)
        self._set(obj, name, val, lambda g: str(g) == str(val))

    def set_bool(self, obj, name, value):
        self._set(obj, name, bool(value), lambda g: bool(g) == bool(value))

    def set_dist(self, module, name, mode, values):
        d = module.get_editor_property(name)
        mode_val = _enum_value(d.get_editor_property("mode"), mode)
        d.set_editor_property("mode", mode_val)
        cur_min = d.get_editor_property("min")
        dim = 1 if isinstance(cur_min, (int, float)) else len([f for f in ("x", "y", "z") if hasattr(cur_min, f)])
        if mode == "UNIFORM_CONSTANT":
            full = [values[0]] * dim
        else:
            if len(values) != dim:
                raise RainRefused("dist_dimension", "%s wants %d values, got %d" % (name, dim, len(values)))
            full = list(values)
        d.set_editor_property("min", _vec_write(d.get_editor_property("min"), full))
        d.set_editor_property("max", _vec_write(d.get_editor_property("max"), full))
        d.set_editor_property("channel_constants_and_ranges", channels_for(mode, values))

        def check(g):
            return (str(g.get_editor_property("mode")) == str(mode_val)
                    and all(_close(a, b) for a, b in zip(_vec_read(g.get_editor_property("min"), dim), full))
                    and all(_close(a, b) for a, b in zip(_vec_read(g.get_editor_property("max"), dim), full)))
        self._set(module, name, d, check)

    def set_color(self, module, name, rgba):
        d = module.get_editor_property(name)
        d.set_editor_property("mode", _enum_value(d.get_editor_property("mode"), "NON_UNIFORM_CONSTANT"))
        d.set_editor_property("values", [self.kit.color(*rgba)])
        d.set_editor_property("channel_constants_and_ranges", [float(c) for c in rgba])

        def check(g):
            vals = list(g.get_editor_property("values"))
            return len(vals) == 1 and all(_close(a, b) for a, b in zip(_vec_read(vals[0], 4), rgba))
        self._set(module, name, d, check)

    def apply(self, spec):
        mods = self.modules()
        for short, body in spec["modules"].items():
            m = mods.get(MOD + short)
            if m is None:
                raise RainRefused("module_absent", MOD + short)
            self.set_bool(m, "module_enabled", True)
            for k, v in body.get("enums", {}).items():
                self.set_enum(m, k, v)
            for k, v in body.get("bools", {}).items():
                self.set_bool(m, k, v)
            for k, (mode, vals) in body.get("dists", {}).items():
                self.set_dist(m, k, mode, vals)
            for k, rgba in body.get("colors", {}).items():
                self.set_color(m, k, rgba)
        for short in spec["disable"]:
            m = mods.get(MOD + short)
            if m is None:
                self.log.append({"obj": MOD + short, "prop": "module_enabled", "ok": True, "got": "absent"})
                continue
            try:
                self.set_bool(m, "module_enabled", False)
            except RainRefused:
                if short in MUST_DISABLE:
                    raise
                self.log.append({"obj": MOD + short, "prop": "module_enabled", "ok": True,
                                 "got": "could not disable (not a force; left as template)"})
        # spawn info: the first RATE entry carries the rate, every other entry is disabled
        infos = list(self.em.get_editor_property("spawn_infos"))
        rate_ix = [i for i, s in enumerate(infos) if "RATE" in str(s.get_editor_property("type")).upper()]
        if not rate_ix:
            if not infos:
                raise RainRefused("no_spawn_info")
            infos[0].set_editor_property("type", _enum_value(infos[0].get_editor_property("type"), "RATE"))
            rate_ix = [0]
        for i, s in enumerate(infos):
            if i == rate_ix[0]:
                s.set_editor_property("enabled", True)
                d = s.get_editor_property("rate")
                d.set_editor_property("mode", _enum_value(d.get_editor_property("mode"), "UNIFORM_CONSTANT"))
                d.set_editor_property("min", float(spec["spawn_rate"]))
                d.set_editor_property("max", float(spec["spawn_rate"]))
                d.set_editor_property("channel_constants_and_ranges", [float(spec["spawn_rate"])])
                s.set_editor_property("rate", d)
            else:
                s.set_editor_property("enabled", False)
        want_rate = float(spec["spawn_rate"])

        def check_infos(g):
            g = list(g)
            if len(g) != len(infos):
                return False
            for i, s in enumerate(g):
                if i == rate_ix[0]:
                    r = s.get_editor_property("rate")
                    if not (bool(s.get_editor_property("enabled")) and _close(r.get_editor_property("min"), want_rate)
                            and _close(r.get_editor_property("max"), want_rate)):
                        return False
                elif bool(s.get_editor_property("enabled")):
                    return False
            return True
        self._set(self.em, "spawn_infos", infos, check_infos)
        # fixed bounds
        fb = self.em.get_editor_property("fixed_bounds")
        fb.set_editor_property("min", _vec_write(fb.get_editor_property("min"), spec["fixed_bounds"]["min"]))
        fb.set_editor_property("max", _vec_write(fb.get_editor_property("max"), spec["fixed_bounds"]["max"]))
        try:
            fb.set_editor_property("is_valid", True)
        except Exception:
            pass

        def check_fb(g):
            return all(_close(a, b) for a, b in zip(_vec_read(g.get_editor_property("min"), 3), spec["fixed_bounds"]["min"])) \
                and all(_close(a, b) for a, b in zip(_vec_read(g.get_editor_property("max"), 3), spec["fixed_bounds"]["max"]))
        self._set(self.em, "fixed_bounds", fb, check_fb)
        # renderer
        rends = [r for r in list(self.em.get_editor_property("renderer_properties"))
                 if r is not None and self.kit.class_name(r) == SPRITE_RENDERER_CLASS]
        if len(rends) != 1:
            raise RainRefused("sprite_renderer_count", len(rends))
        r = rends[0]
        for k, v in spec["renderer"]["enums"].items():
            self.set_enum(r, k, v)
        if spec["renderer"].get("material"):
            mat = self.kit.load(spec["renderer"]["material"])
            self._set(r, "material", mat, lambda g: self.kit.name(g) == self.kit.name(mat))
        # re-set the module list so the EMITTER's PostEditChangeProperty runs after the module edits
        # [inferred: NiagaraStatelessEmitter.h:44 declares it; the .cpp that rebuilds the emitter data is not here]
        mods_list = list(self.em.get_editor_property("modules"))
        self._set(self.em, "modules", mods_list, lambda g: len(list(g)) == len(mods_list))
        return self.log


# ---- step guards (pure)

def census_clean(c):
    return c == {"content": [], "maps": []}


def guard_probe(pie_running):
    if pie_running:
        raise RainRefused("pie_running", "PROBE runs in the editor world")


def guard_create(pie_running, census, existing, probe):
    if pie_running:
        raise RainRefused("pie_running")
    if not census_clean(census):
        raise RainRefused("census_dirty", json.dumps(census))
    if existing:
        raise RainRefused("asset_exists", ",".join(existing))
    if not probe or probe.get("template") != TEMPLATE:
        raise RainRefused("no_probe", "run PROBE first")
    if not probe.get("authorable"):
        raise RainRefused("probe_not_authorable", ",".join(probe.get("missing", [])[:8]))


def guard_pie_begin(pie_running, census, create):
    if pie_running:
        raise RainRefused("pie_running")
    if not create or create.get("status") != "created":
        raise RainRefused("no_create", "CREATE has not completed")
    allowed = set(create.get("created", []))
    if census.get("maps"):
        raise RainRefused("map_dirty", ",".join(census["maps"]))
    foreign = sorted(set(census.get("content", [])) - allowed)
    if foreign:
        raise RainRefused("foreign_dirty_content", ",".join(foreign))


def guard_setup(world_kind, create, live_paths, handles):
    if world_kind != "game":
        raise RainRefused("no_pie", "PIE_BEGIN first")
    if not create or create.get("status") != "created":
        raise RainRefused("no_create")
    if live_paths:
        raise RainRefused("already_set_up", "%d bench components live in PIE" % len(live_paths))
    if handles:
        raise RainRefused("tick_armed", ",".join(handles))


def guard_stills(world_kind, setup, live_paths, handles):
    if world_kind != "game":
        raise RainRefused("no_pie")
    if not setup or setup.get("status") not in ("set_up", "stills_armed"):
        raise RainRefused("no_setup")
    want = sorted(r["path"] for r in setup.get("spawned", []))
    if sorted(live_paths) != want:
        raise RainRefused("components_changed", "live %d, recorded %d" % (len(live_paths), len(want)))
    if handles:
        raise RainRefused("tick_armed", ",".join(handles))


def deletable_assets(create):
    """Only assets the create record says the BENCH created, in the bench folder, with a ZZ_ name."""
    out = []
    for path in (create or {}).get("created", []):
        name = path.rsplit("/", 1)[-1]
        if path in BENCH_ASSETS and path.startswith(BENCH_FOLDER + "/") and "_ZZ_" in name:
            out.append(path)
        else:
            raise RainRefused("refuse_delete_foreign", path)
    return out


def guard_teardown(pie_running, create):
    if pie_running:
        raise RainRefused("pie_running", "end PIE first (conductor_pie_end.py)")
    return deletable_assets(create)


# ---- flows (engine-free; adapters injected)

def flow_setup(adapter, p, create, run, log=print, record_path=None):
    """Plan, write the record (with spawned=[]) BEFORE the first spawn, spawn, record each, census gate."""
    record_path = record_path or SETUP_RECORD
    guard_setup(adapter.world_kind(), create, adapter.live_component_paths(), adapter.armed_handles())
    census_before = adapter.census()
    seg = adapter.segment(p["passage"])
    tps = adapter.tick_resolution()
    strobe = pick_strobe(adapter.strobes(), seg["guid"], p) if p.get("flash") else None
    rows, flash = plan_fractions((seg["start"], seg["end"]), tps, strobe, p)
    fractions = [r["fraction"] for r in rows]
    plan = plan_tiles(fractions, p)
    summary = check_plan(plan, fractions, p)
    systems = [NS_RAIN] + ([NS_SPLASH] if p.get("splash") and NS_SPLASH in create.get("created", []) else [])
    rec = {"run": run, "status": "spawning", "params": p, "segment": seg, "tick_resolution": tps,
           "strobes_seen": adapter.strobes(), "strobe": strobe, "flash": flash, "stills_plan": rows,
           "fractions": fractions, "plan": plan, "summary": summary, "systems": systems, "spawned": [],
           "census_before": census_before, "world": adapter.world_name(), "stills_runs": {}, "visibility": "shown"}
    write_record(record_path, rec, log)
    for sys_path in systems:
        for i, t in enumerate(plan["tiles"]):
            loc = list(t["center"])
            if sys_path == NS_SPLASH:
                loc[2] = float(p["floor_z"]) + 2.0
            path = adapter.spawn(sys_path, loc)
            rec["spawned"].append({"system": sys_path, "tile": i, "location": loc, "path": path})
            write_record(record_path, rec, lambda *_: None)
    live = adapter.live_component_paths()
    if sorted(live) != sorted(r["path"] for r in rec["spawned"]):
        rec["status"] = "spawn_mismatch"
        write_record(record_path, rec, log)
        raise RainRefused("spawn_mismatch", "live %d, spawned %d" % (len(live), len(rec["spawned"])), run, "SETUP")
    census_after = adapter.census()
    rec["census_after"] = census_after
    if census_after != census_before:
        rec["status"] = "census_changed"
        write_record(record_path, rec, log)
        raise RainRefused("census_changed", "%r -> %r" % (census_before, census_after), run, "SETUP")
    rec["status"] = "set_up"
    write_record(record_path, rec, log)
    return rec


def flow_teardown_pie(adapter, setup, run, log=print, record_path=None):
    record_path = record_path or SETUP_RECORD
    if adapter.world_kind() != "game":
        raise RainRefused("no_pie", "nothing to tear down in PIE (PIE end already destroyed the PIE world)", run,
                          "TEARDOWN_PIE")
    census_before = adapter.census()
    paths = sorted(set([r["path"] for r in (setup or {}).get("spawned", [])] + adapter.live_component_paths()))
    destroyed, failed = [], []
    for path in paths:
        try:
            ok = adapter.destroy(path)
        except Exception as exc:          # recorded; the post-sweep decides
            ok = False
            failed.append("%s: %s" % (path, exc))
        (destroyed if ok else failed).append(path)
    left = adapter.live_component_paths()
    census_after = adapter.census()
    out = {"destroyed": destroyed, "failed": failed, "left": left, "census_before": census_before,
           "census_after": census_after}
    if setup is not None:
        setup["teardown_pie"] = out
        setup["status"] = "torn_down_pie" if not left else "teardown_pie_left_components"
        write_record(record_path, setup, log)
    if left:
        raise RainRefused("components_left", ",".join(left), run, "TEARDOWN_PIE")
    if census_after != census_before:
        raise RainRefused("census_changed", "%r -> %r" % (census_before, census_after), run, "TEARDOWN_PIE")
    return out


def flow_teardown(adapter, create, p, run, log=print, record_path=None):
    """Editor world, PIE off: sweep, delete only bench-created assets, require a clean census."""
    record_path = record_path or TEARDOWN_RECORD
    to_delete = guard_teardown(adapter.pie_running(), create)
    rec = {"run": run, "status": "tearing_down", "census_before": adapter.census(),
           "editor_components": adapter.live_component_paths(), "to_delete": to_delete, "deleted": [],
           "delete_failed": []}
    write_record(record_path, rec, log)
    for path in rec["editor_components"]:
        adapter.destroy(path)
    rec["editor_components_left"] = adapter.live_component_paths()
    if p.get("delete_assets", True):
        # systems first (they reference the material), then the material
        for path in sorted(to_delete, key=lambda s: (s == M_STREAK, s)):
            if not adapter.asset_exists(path):
                rec["deleted"].append(path + " (already gone)")
                continue
            ok = adapter.delete_asset(path)
            (rec["deleted"] if ok and not adapter.asset_exists(path) else rec["delete_failed"]).append(path)
    rec["census_after"] = adapter.census()
    clean = census_clean(rec["census_after"]) and not rec["delete_failed"] and not rec["editor_components_left"]
    rec["status"] = "clean" if clean else "needs_dont_save_restart"
    write_record(record_path, rec, log)
    if create is not None and CREATE_RECORD.exists() and record_path == TEARDOWN_RECORD:
        create["status"] = "torn_down" if clean else "teardown_incomplete"
        write_record(CREATE_RECORD, create, log)
    return rec


# ---- VERIFY (pure; runs offline)

def png_pixels(path):
    """(w, h, bpp, rows) of an 8-bit non-interlaced PNG; the decoder of passage_stills.png_luma, kept rows."""
    data = pathlib.Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, head = 8, [], None
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        typ, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    w, h, depth, ctype, _c, _f, interlace = head
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        raise ValueError("unsupported PNG")
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    prev, rows = bytearray(stride), []
    for y in range(h):
        base = y * (stride + 1)
        ft = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ft == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        elif ft != 0:
            raise ValueError("bad filter")
        rows.append(bytes(line))
        prev = line
    return w, h, bpp, rows


def mean_abs_diff(path_a, path_b):
    wa, ha, ba, ra = png_pixels(path_a)
    wb, hb, bb, rb = png_pixels(path_b)
    if (wa, ha, ba) != (wb, hb, bb):
        raise ValueError("size mismatch %s vs %s" % ((wa, ha, ba), (wb, hb, bb)))
    tot = 0
    for x, y in zip(ra, rb):
        tot += sum(abs(i - j) for i, j in zip(x, y))
    return tot / float(wa * ha * ba)


def verify(setup, p, manifest_loader=None, diff=mean_abs_diff):
    """Returns (ok, report). Reads the stills manifests named in the setup record."""
    load = manifest_loader or (lambda d: json.loads((pathlib.Path(d) / ps.MANIFEST_NAME).read_text(encoding="utf-8")))
    rep = {"checks": [], "problems": []}

    def chk(name, cond, detail=""):
        rep["checks"].append({"name": name, "ok": bool(cond), "detail": detail})
        if not cond:
            rep["problems"].append(name + (": " + str(detail) if detail else ""))
    runs = (setup or {}).get("stills_runs", {})
    chk("rain stills run recorded", "rain" in runs)
    if "rain" not in runs:
        return False, rep
    rain = load(runs["rain"])
    chk("rain manifest passed", rain.get("status") == "passed", rain.get("status"))
    tiles = setup["plan"]["tiles"]
    kinds = {round(r["fraction"], 9): r["kind"] for r in setup["stills_plan"]}
    by_kind = {}
    for s in rain.get("stills", []):
        kind = kinds.get(round(s["fraction"], 9), "?")
        by_kind.setdefault(kind, []).append(s)
        pose = s.get("pose") or {}
        loc = pose.get("loc")
        chk("still %d pose recorded" % s["i"], loc is not None)
        if loc is None:
            continue
        on_route = (abs(loc[1] - p["route"]["y"]) <= p["route_tol_cm"] and abs(loc[2] - p["route"]["z"]) <= p["route_tol_cm"]
                    and abs(loc[0] - route_x(s["fraction"], p["route"])) <= p["route_tol_cm"])
        chk("still %d camera on the planned route" % s["i"], on_route, loc)
        cov = view_coverage(pose, tiles, p)
        s["rain_coverage"] = round(cov, 3)
        chk("still %d rain covers the actual view (%.2f)" % (s["i"], cov), cov >= p["min_view_coverage"], cov)
    flash = setup.get("flash")
    if flash:
        tps = setup["tick_resolution"]
        f_rows, d_rows = by_kind.get("flash", []), by_kind.get("dark", [])
        chk("flash and dark stills present", len(f_rows) == 1 and len(d_rows) == 1)
        if len(f_rows) == 1 and len(d_rows) == 1:
            fr = f_rows[0].get("master_frame_at_capture")
            lvl = strobe_level_at_frame(fr, tps, flash["strobe"]) if fr is not None else -1
            chk("flash still was taken at strobe level 1 (frame %s)" % fr, lvl >= 1.0, lvl)
            lf, ld = f_rows[0].get("luma"), d_rows[0].get("luma")
            chk("flash still brighter than its dark partner", lf is not None and ld is not None
                and lf - ld >= p["min_flash_delta"], "%s vs %s" % (lf, ld))
    else:
        rep["notes"] = ["no strobe flash still: " + ("flash disabled" if not p.get("flash") else
                                                       "no enabled strobe active in P04 on the route")]
    if "norain" in runs:
        nr = load(runs["norain"])
        chk("norain manifest passed", nr.get("status") == "passed", nr.get("status"))
        pairs = {round(s["fraction"], 9): s for s in nr.get("stills", [])}
        for s in rain.get("stills", []):
            o = pairs.get(round(s["fraction"], 9))
            if o is None:
                chk("still %d has a norain partner" % s["i"], False)
                continue
            d = diff(s["path"], o["path"])
            s["rain_minus_norain"] = round(d, 3)
            chk("still %d rain visible (mean |diff| %.2f)" % (s["i"], d), d >= p["min_rain_diff"], d)
    else:
        chk("norain run present", not p.get("require_norain"), "require_norain is set")
    rep["stills"] = rain.get("stills", [])
    return not rep["problems"], rep


# --------------------------------------------------------------------------
# Unreal side. Everything below runs only inside the editor; Unreal objects stay inside these functions.
# --------------------------------------------------------------------------

def _census(unreal):
    lib = unreal.EditorLoadingAndSavingUtils
    return {"maps": ps.package_names(lib.get_dirty_map_packages()),
            "content": ps.package_names(lib.get_dirty_content_packages())}


def _iter(unreal, cls):
    it = getattr(unreal, "ObjectIterator", None)
    if it is None:
        raise RainRefused("no_object_iterator", "unreal.ObjectIterator missing")
    return list(it(cls))


def _sub_objects(unreal, owner, cls_name):
    cls = getattr(unreal, cls_name, None)
    if cls is None:
        raise RainRefused("class_not_exposed", cls_name)
    root = owner.get_path_name()
    return [o for o in _iter(unreal, cls) if str(o.get_path_name()).startswith((root + ":", root + "."))]


def _bench_components(unreal, pie):
    """Object paths of live NiagaraComponents whose system is a bench asset; pie=True: PIE worlds only."""
    out = []
    for c in _iter(unreal, unreal.NiagaraComponent):
        try:
            asset = c.get_asset()
            apath = str(asset.get_path_name()).split(".", 1)[0] if asset is not None else ""
            path = str(c.get_path_name())
        except Exception:
            continue
        if apath not in (NS_RAIN, NS_SPLASH) or path.startswith("/Engine/Transient"):
            continue
        if not unreal.SystemLibrary.is_valid(c):
            continue
        if ("UEDPIE_" in path) == bool(pie):
            out.append(path)
    return sorted(out)


class _Kit:
    def __init__(self, unreal):
        self.u = unreal

    def name(self, obj):
        return str(obj.get_path_name()) if hasattr(obj, "get_path_name") else str(obj)

    def class_name(self, obj):
        return str(obj.get_class().get_name())

    def show(self, v):
        try:
            return str(v)[:200]
        except Exception:
            return "?"

    def color(self, r, g, b, a):
        return self.u.LinearColor(r, g, b, a)

    def load(self, path):
        obj = self.u.EditorAssetLibrary.load_asset(path)
        if obj is None:
            raise RainRefused("load_failed", path)
        return obj


def _probe_object(obj, props, kit):
    rows = []
    for prop in props:
        optional = prop.endswith("?")
        name = prop.rstrip("?")
        try:
            v = obj.get_editor_property(name)
            row = {"prop": name, "ok": True, "type": type(v).__name__, "value": kit.show(v)}
            if hasattr(v, "get_editor_property"):          # a distribution: record its layout evidence
                sub = {}
                for f in ("mode", "min", "max", "channel_constants_and_ranges", "values"):
                    try:
                        sub[f] = kit.show(v.get_editor_property(f))
                    except Exception as exc:
                        sub[f] = "ERR %s" % exc
                row["fields"] = sub
                need = ("mode", "values") if name == "color_distribution" else ("mode", "min", "max")
                row["ok"] = all(not str(sub[f]).startswith("ERR") for f in need)
            rows.append(row)
        except Exception as exc:
            rows.append({"prop": name, "ok": optional, "error": "%s: %s" % (type(exc).__name__, exc)})
    return rows


def mode_probe(unreal, p, log):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    guard_probe(ed.get_game_world() is not None)
    run = "PROBE-" + utc_stamp()
    log("%s_PROBE_START|run=%s|template=%s" % (MARK, run, TEMPLATE))
    kit = _Kit(unreal)
    rec = {"run": run, "template": TEMPLATE, "authorable": False, "missing": [], "census_before": _census(unreal),
           "assets_in_bench_folder": [a for a in BENCH_ASSETS if unreal.EditorAssetLibrary.does_asset_exist(a)]}
    system = unreal.EditorAssetLibrary.load_asset(TEMPLATE.split(".", 1)[0])
    rec["template_loaded"] = system is not None and type(system).__name__ == "NiagaraSystem"
    if not rec["template_loaded"]:
        rec["missing"].append("template:" + TEMPLATE)
    else:
        try:
            emitters = _sub_objects(unreal, system, STATELESS_EMITTER_CLASS)
        except RainRefused as exc:
            emitters, rec["emitter_error"] = [], str(exc)
        rec["stateless_emitters"] = [kit.name(e) for e in emitters]
        if len(emitters) != 1:
            rec["missing"].append("one_stateless_emitter(found %d)" % len(emitters))
        else:
            em = emitters[0]
            spec = rain_spec(p, M_STREAK)
            by_owner = {}
            for owner, prop in probe_paths(spec):
                by_owner.setdefault(owner, []).append(prop)
            rec["emitter"] = _probe_object(em, by_owner.pop("emitter"), kit)
            mods = {}
            try:
                mods = {kit.class_name(m): m for m in list(em.get_editor_property("modules")) if m is not None}
            except Exception as exc:
                rec["modules_error"] = str(exc)
            rec["module_classes"] = sorted(mods)
            rends = []
            try:
                rends = [r for r in list(em.get_editor_property("renderer_properties"))
                         if r is not None and kit.class_name(r) == SPRITE_RENDERER_CLASS]
            except Exception as exc:
                rec["renderer_error"] = str(exc)
            rec["renderer"] = _probe_object(rends[0], by_owner.pop("renderer"), kit) if len(rends) == 1 else \
                [{"prop": "sprite_renderer", "ok": False, "error": "found %d" % len(rends)}]
            rec["modules"] = {}
            for owner, props in by_owner.items():
                m = mods.get(owner)
                if m is None:
                    optional = all(x.endswith("?") for x in props)
                    rec["modules"][owner] = [{"prop": "(module)", "ok": optional, "error": "absent"}]
                else:
                    rec["modules"][owner] = _probe_object(m, props, kit)
            try:
                infos = list(em.get_editor_property("spawn_infos"))
                rec["spawn_infos"] = [{"type": kit.show(s.get_editor_property("type")),
                                       "enabled": kit.show(s.get_editor_property("enabled")),
                                       "rate": kit.show(s.get_editor_property("rate").get_editor_property("min"))}
                                      for s in infos]
            except Exception as exc:
                rec["spawn_infos"] = "ERR %s: %s" % (type(exc).__name__, exc)
                rec["missing"].append("emitter.spawn_infos[].type/enabled/rate")
            try:
                rec["emitter_state"] = kit.show(em.get_editor_property("emitter_state"))
            except Exception as exc:
                rec["emitter_state"] = "ERR %s" % exc
            for row in rec["emitter"] + rec["renderer"]:
                if not row["ok"]:
                    rec["missing"].append("emitter_or_renderer." + row["prop"])
            for owner, rows in rec["modules"].items():
                for row in rows:
                    if not row["ok"]:
                        rec["missing"].append(owner + "." + row["prop"])
    for cls in ("NiagaraFunctionLibrary", "NiagaraComponent", "NCPoolMethod", "ObjectIterator"):
        if getattr(unreal, cls, None) is None:
            rec["missing"].append("unreal." + cls)
    lib = getattr(unreal, "NiagaraFunctionLibrary", None)
    if lib is not None and not hasattr(lib, "spawn_system_at_location"):
        rec["missing"].append("NiagaraFunctionLibrary.spawn_system_at_location")
    rec["authorable"] = not rec["missing"]
    rec["census_after"] = _census(unreal)
    if rec["census_after"] != rec["census_before"]:
        rec["missing"].append("probe dirtied %r" % rec["census_after"])
        rec["authorable"] = False
    write_record(PROBE_RECORD, rec, log)
    log("%s_PROBE_OK|run=%s|authorable=%s|missing=%d|first=%s|record=%s" % (
        MARK, run, "yes" if rec["authorable"] else "no", len(rec["missing"]),
        ";".join(rec["missing"][:6]), PROBE_RECORD.as_posix()))
    return rec


def _create_material(unreal, log):
    folder, name = M_STREAK.rsplit("/", 1)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    if mat is None:
        raise RainRefused("material_create_failed", M_STREAK)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("translucency_lighting_mode",
                            unreal.TranslucencyLightingMode.TLM_VOLUMETRIC_PER_VERTEX_NON_DIRECTIONAL)
    mat.set_editor_property("two_sided", True)
    usage = None
    for nm in ("used_with_niagara_sprites", "b_used_with_niagara_sprites"):
        try:
            mat.set_editor_property(nm, True)
            usage = bool(mat.get_editor_property(nm))
            break
        except Exception:
            continue
    if not usage:
        raise RainRefused("material_niagara_usage", "used_with_niagara_sprites not set")
    mel = unreal.MaterialEditingLibrary
    pc = mel.create_material_expression(mat, unreal.MaterialExpressionParticleColor, -500, 0)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -500, 200)
    rough.set_editor_property("r", 0.08)
    ok = [mel.connect_material_property(pc, "RGB", unreal.MaterialProperty.MP_BASE_COLOR),
          mel.connect_material_property(pc, "A", unreal.MaterialProperty.MP_OPACITY),
          mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)]
    mel.recompile_material(mat)
    back = {"blend_mode": str(mat.get_editor_property("blend_mode")),
            "shading_model": str(mat.get_editor_property("shading_model")),
            "expressions": int(mel.get_num_material_expressions(mat)), "connect_returns": ok}
    if "TRANSLUCENT" not in back["blend_mode"] or back["expressions"] != 2:
        raise RainRefused("material_readback", json.dumps(back))
    log("%s_MATERIAL|path=%s|%s|compile is async: check the log for 'Failed to compile' ~20 s later" % (
        MARK, M_STREAK, json.dumps(back)))
    return back


def mode_create(unreal, p, log):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eal = unreal.EditorAssetLibrary
    existing = [a for a in BENCH_ASSETS if eal.does_asset_exist(a)]
    guard_create(ed.get_game_world() is not None, _census(unreal), existing, read_record(PROBE_RECORD))
    run = "RAIN-" + utc_stamp()
    planned = [NS_RAIN] + ([M_STREAK] if p["material"] == "bench_lit" else []) + ([NS_SPLASH] if p["splash"] else [])
    rec = {"run": run, "status": "creating", "template": TEMPLATE, "params": p, "planned": planned, "created": [],
           "sets": {}, "census_before": _census(unreal)}
    write_record(CREATE_RECORD, rec, log)          # the plan is on disk before the first create
    log("%s_CREATE_START|run=%s|planned=%s" % (MARK, run, ",".join(planned)))
    kit, tools = _Kit(unreal), unreal.AssetToolsHelpers.get_asset_tools()
    try:
        mat_path = None
        if p["material"] == "bench_lit":
            rec["created"].append(M_STREAK)
            write_record(CREATE_RECORD, rec, log)
            rec["material"] = _create_material(unreal, log)
            mat_path = M_STREAK
        template = eal.load_asset(TEMPLATE.split(".", 1)[0])
        for path, spec in ((NS_RAIN, rain_spec(p, mat_path)),) + (((NS_SPLASH, splash_spec(p, mat_path)),)
                                                                  if p["splash"] else ()):
            folder, name = path.rsplit("/", 1)
            rec["created"].append(path)
            write_record(CREATE_RECORD, rec, log)
            system = tools.duplicate_asset(name, folder, template)
            if system is None or not eal.does_asset_exist(path):
                raise RainRefused("duplicate_failed", path)
            ems = _sub_objects(unreal, system, STATELESS_EMITTER_CLASS)
            if len(ems) != 1:
                raise RainRefused("emitter_count", "%s: %d" % (path, len(ems)))
            rec["sets"][path] = []
            Retuner(ems[0], kit, rec["sets"][path]).apply(spec)
            rec["spec_" + name] = spec
            write_record(CREATE_RECORD, rec, log)
        census = _census(unreal)
        rec["census_after"] = census
        if census["maps"] or not set(census["content"]) <= set(rec["created"]):
            raise RainRefused("create_dirtied_foreign", json.dumps(census))
        rec["status"] = "created"
        write_record(CREATE_RECORD, rec, log)
        log("%s_CREATE_OK|run=%s|assets=%s|sets=%d|dirty=%s|NOT SAVED (PIE_BEGIN allows exactly these)" % (
            MARK, run, ",".join(rec["created"]), sum(len(v) for v in rec["sets"].values()),
            ",".join(census["content"])))
        return rec
    except Exception as exc:
        rec["status"] = "create_failed"
        rec["error"] = traceback.format_exc()
        rolled = []
        for path in reversed(deletable_assets(rec)):
            try:
                if eal.does_asset_exist(path) and eal.delete_asset(path) and not eal.does_asset_exist(path):
                    rolled.append(path)
            except Exception:
                rec["error"] += "\nrollback " + path + ": " + traceback.format_exc()
        rec["rolled_back"] = rolled
        rec["census_after_rollback"] = _census(unreal)
        write_record(CREATE_RECORD, rec, log)
        reason = getattr(exc, "reason", type(exc).__name__)
        raise RainRefused(reason, "%s|rolled_back=%s|census=%s" % (getattr(exc, "detail", exc), ",".join(rolled),
                                                                  json.dumps(rec["census_after_rollback"])),
                          run, "CREATE") from exc


def mode_pie_begin(unreal, p, log):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    create = read_record(CREATE_RECORD)
    guard_pie_begin(ed.get_game_world() is not None, _census(unreal), create)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    log("%s_PIE_BEGIN_REQUESTED|run=%s|allowed_dirty=%s" % (MARK, create["run"], ",".join(create["created"])))


def make_rain_pie_adapter(unreal):
    """PIE reads + the Niagara component spawn/destroy. No actor is spawned anywhere."""
    base = ps.make_pie_adapter(unreal)
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

    def world():
        w = editor_sub.get_game_world()
        if w is None or base.world_kind() != "game":
            raise RainRefused("pie_ended")
        return w

    def root():
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.InfinityStageShowRoot))
        if len(roots) != 1:
            raise RainRefused("no_show_root", len(roots))
        return roots[0]

    class A:
        def world_kind(self):
            return base.world_kind()

        def world_name(self):
            return base.world_name()

        def census(self):
            return base.census()

        def armed_handles(self):
            import builtins
            return ps.armed_handles(builtins)

        def segment(self, passage):
            n, label = ps.passage_label(passage)
            segs = [s for s in list(root().transport.segments)
                    if s.type == unreal.InfinityCueType.WING_PAIR and str(s.label) == label]
            if len(segs) != 1:
                raise RainRefused("no_segment", "%s: %d" % (label, len(segs)))
            s = segs[0]
            return {"label": label, "start": int(s.start_frame.value), "end": int(s.end_frame.value),
                    "guid": str(s.segment_guid)}

        def tick_resolution(self):
            fr = root().show_asset.get_editor_property("tick_resolution")
            num, den = int(fr.numerator), int(fr.denominator)
            if den != 1:
                raise RainRefused("tick_resolution", "%d/%d" % (num, den))
            return num

        def strobes(self):
            cls = getattr(unreal, "InfinityStageStrobeLight", None)
            rows = []
            if cls is None:
                return rows
            for a in unreal.GameplayStatics.get_all_actors_of_class(world(), cls):
                loc = a.get_actor_location()
                try:
                    label = str(a.get_actor_label())
                except Exception:
                    label = str(a.get_name())
                rows.append({"label": label, "location": [float(loc.x), float(loc.y), float(loc.z)],
                             "enabled": bool(a.get_editor_property("strobe_enabled")),
                             "period_seconds": float(a.get_editor_property("period_seconds")),
                             "flash_seconds": float(a.get_editor_property("flash_seconds")),
                             "decay_seconds": float(a.get_editor_property("decay_seconds")),
                             "phase_cycles": float(a.get_editor_property("phase_cycles")),
                             "peak_intensity": float(a.get_editor_property("peak_intensity")),
                             "active_segment_guids": [str(g) for g in a.get_editor_property("active_segment_guids")]})
            return rows

        def live_component_paths(self):
            return _bench_components(unreal, pie=True)

        def spawn(self, system_path, loc):
            system = unreal.EditorAssetLibrary.load_asset(system_path)
            if system is None:
                raise RainRefused("system_missing", system_path)
            comp = unreal.NiagaraFunctionLibrary.spawn_system_at_location(
                world(), system, unreal.Vector(*loc), unreal.Rotator(0.0, 0.0, 0.0), unreal.Vector(1.0, 1.0, 1.0),
                False, True, unreal.NCPoolMethod.NONE, False)
            if comp is None:
                raise RainRefused("spawn_returned_none", system_path)
            path = str(comp.get_path_name())
            if "UEDPIE_" not in path:
                comp.destroy_component(comp.get_owner() or comp)
                raise RainRefused("spawned_outside_pie", path)
            return path

        def _find(self, path):
            comp = unreal.find_object(None, path)
            return comp if comp is not None and unreal.SystemLibrary.is_valid(comp) else None

        def destroy(self, path):
            comp = self._find(path)
            if comp is None:
                return True
            try:
                comp.deactivate_immediate()
            except Exception:
                comp.deactivate()
            comp.destroy_component(comp.get_owner() or comp)
            return self._find(path) is None

        def set_visible(self, path, visible):
            comp = self._find(path)
            if comp is None:
                raise RainRefused("component_gone", path)
            comp.set_visibility(bool(visible), True)
            return bool(comp.is_visible()) == bool(visible)

    return A()


def make_editor_adapter(unreal):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eal = unreal.EditorAssetLibrary

    class E:
        def pie_running(self):
            return ed.get_game_world() is not None

        def census(self):
            return _census(unreal)

        def live_component_paths(self):
            return _bench_components(unreal, pie=False)

        def destroy(self, path):
            comp = unreal.find_object(None, path)
            if comp is not None:
                comp.destroy_component(comp.get_owner() or comp)
            return True

        def asset_exists(self, path):
            return bool(eal.does_asset_exist(path))

        def delete_asset(self, path):
            return bool(eal.delete_asset(path))

    return E()


def mode_setup(unreal, p, log):
    create = read_record(CREATE_RECORD)
    run = (create or {}).get("run", "?")
    rec = flow_setup(make_rain_pie_adapter(unreal), p, create, run, log)
    log("%s_SETUP_OK|run=%s|components=%d|tiles=%d|live_particles~%d|fractions=%s|strobe=%s|flash_frame=%s|record=%s" % (
        MARK, run, len(rec["spawned"]), len(rec["plan"]["tiles"]), rec["summary"]["live_particles"],
        ",".join("%.4f" % f for f in rec["fractions"]), (rec["strobe"] or {}).get("label", "none"),
        (rec["flash"] or {}).get("flash_frame", "none"), SETUP_RECORD.as_posix()))
    return rec


def mode_stills(unreal, p, log, rain_on=True):
    import builtins
    adapter = make_rain_pie_adapter(unreal)
    setup = read_record(SETUP_RECORD)
    run = (setup or {}).get("run", "?")
    guard_stills(adapter.world_kind(), setup, adapter.live_component_paths(), ps.armed_handles(builtins))
    want = "shown" if rain_on else "hidden"
    if setup.get("visibility") != want:
        setup["visibility_change"] = {"from": setup.get("visibility"), "to": want}
        setup["visibility"] = "changing"
        write_record(SETUP_RECORD, setup, log)       # recorded before the change
        bad = [r["path"] for r in setup["spawned"] if not adapter.set_visible(r["path"], rain_on)]
        if bad:
            raise RainRefused("visibility_readback", ",".join(bad), run, "STILLS")
        setup["visibility"] = want
    label = "rain" if rain_on else "norain"
    stills = ps.arm(ps.make_pie_adapter(unreal), p["passage"], setup["fractions"], label, dict(p["stills_params"]),
                    register=unreal.register_slate_post_tick_callback,
                    unregister=unreal.unregister_slate_post_tick_callback)
    setup["stills_runs"][label] = stills["run_dir"]
    setup["status"] = "stills_armed"
    write_record(SETUP_RECORD, setup, log)
    log("%s_STILLS_ARMED|run=%s|label=%s|stills_run=%s|n=%d|wait_for=PASSAGE_STILLS_OK|run=%s" % (
        MARK, run, label, stills["run_id"], len(setup["fractions"]), stills["run_id"]))


def mode_teardown_pie(unreal, p, log):
    setup = read_record(SETUP_RECORD)
    run = (setup or {}).get("run", "?")
    out = flow_teardown_pie(make_rain_pie_adapter(unreal), setup, run, log)
    log("%s_TEARDOWN_PIE_OK|run=%s|destroyed=%d|left=0|census=%s|next=conductor_pie_end.py then TEARDOWN" % (
        MARK, run, len(out["destroyed"]), json.dumps(out["census_after"])))


def mode_teardown(unreal, p, log):
    create = read_record(CREATE_RECORD)
    run = (create or {}).get("run", "?")
    rec = flow_teardown(make_editor_adapter(unreal), create, p, run, log)
    if rec["status"] == "clean":
        log("%s_TEARDOWN_OK|run=%s|deleted=%s|census=%s" % (MARK, run, ",".join(rec["deleted"]),
                                                            json.dumps(rec["census_after"])))
    else:
        log("%s_NEEDS_DONT_SAVE_RESTART|run=%s|census=%s|delete_failed=%s|record=%s" % (
            MARK, run, json.dumps(rec["census_after"]), ",".join(rec["delete_failed"]), TEARDOWN_RECORD.as_posix()))


def mode_verify(p, log=print):
    setup = read_record(SETUP_RECORD)
    run = (setup or {}).get("run", "?")
    ok, rep = verify(setup, p)
    rep["run"] = run
    rep["ok"] = ok
    write_record(VERIFY_RECORD, rep, log)
    if ok:
        log("%s_VERIFY_OK|run=%s|checks=%d|record=%s" % (MARK, run, len(rep["checks"]), VERIFY_RECORD.as_posix()))
    else:
        log("%s_FAILED|run=%s|step=VERIFY|reason=%s|record=%s" % (MARK, run, ";".join(rep["problems"][:6]),
                                                                   VERIFY_RECORD.as_posix()))
    return ok, rep


def main():
    g = globals()
    mode = str(g.get("BENCH_MODE", "")).upper()
    if mode not in MODES:
        raise RainRefused("bad_mode", mode)
    p = params_of(g.get("BENCH_PARAMS"))
    if mode == "VERIFY":
        try:
            import unreal
            log = unreal.log
        except ImportError:
            log = print
        return mode_verify(p, log)
    import unreal
    log = unreal.log
    try:
        return {"PROBE": mode_probe, "CREATE": mode_create, "PIE_BEGIN": mode_pie_begin, "SETUP": mode_setup,
                "STILLS": mode_stills, "TEARDOWN_PIE": mode_teardown_pie, "TEARDOWN": mode_teardown,
                "STILLS_NORAIN": lambda u, pp, lg: mode_stills(u, pp, lg, rain_on=False)}[mode](unreal, p, log)
    except RainRefused as exc:
        msg = str(exc) if exc.step != "?" else str(RainRefused(exc.reason, exc.detail,
                                                               (read_record(CREATE_RECORD) or {}).get("run", "?"),
                                                               mode))
        unreal.log_error(msg)
        raise


if "BENCH_MODE" in globals():
    main()
elif __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
    _ok, _rep = mode_verify(params_of(json.loads(sys.argv[2]) if len(sys.argv) > 2 else None))
    sys.exit(0 if _ok else 1)
