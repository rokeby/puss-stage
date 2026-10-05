"""P02 FOG BENCH: a reversible, NON-SAVING side-by-side of fog / contrast fixes on P02, captured as
stills Gary picks from (Gary, 5 Oct, P02 PIE: "the wings do tend to look quite flat ... adjust lighting in this
fog that doesn't only become a big blur of light ... an overall lack of reflectivity").

Variants, each applied from the recorded base and captured at TWO camera positions (P02 bay ~8, first half,
theatrical + lurid; P02 bay ~15, the failing stretch + office tubes):
  base  nothing changed
  A     haze only on hero beams: volumetric_scattering_intensity 0 on every local light within a_radius_cm of the
        camera EXCEPT the a_keep_beams nearest in-view lamps whose label holds BEAM (their value is kept)
  B     low ground mist instead of passage-wide haze: every ExponentialHeightFog's FogDensity and second-fog density
        x b_fog_density_scale; Effect-Source media (local fog) near the camera to 0; b_mist_count prepared
        ZZ_P02FOG_MIST_* Local Fog Volumes placed ahead of the camera, centred on the floor, radial density 0,
        height density b_mist_density falling to b_mist_top_fraction at b_mist_top_cm. Volumetric fog stays ON by
        default: LFVs are voxelised into volumetric fog (and so lit by the bay's lamps) only when it is on
        (VolumetricFog.usf:193-267); outside it an LFV sees only the directional light, sky and emissive
        (LocalFogVolumeCommon.ush:304-323) [declaration-proven, engine shader source]. b_volumetric="off" also
        turns it off.
  C     rake the wings: the LOW_SIDE lamps of bays bay-1 .. bay+4 re-aimed IN PIE ONLY (actor rotation, recorded,
        restored; the Show asset is never touched): even layers graze their own side's wing at c_graze_deg off the
        route (forward or back), odd layers aim at the floor at their foot (dark layer). Light and dark alternate
        in depth.
  D     exposure lock: AutoExposureMin = Max = the base state's EV on every post-process source that affects the
        camera. The EV is not readable from Python (FSceneView::GetLastEyeAdaptationExposure is C++ only,
        SceneView.h:2147) so it is MEASURED by bisection: lock at a trial EV, settle, compare the median luma with
        the base's, halve the interval [d_cal_iters steps]. If the base is already locked (min == max) D only
        records that (P02_FOG_BENCH_D_ALREADY_LOCKED).
  E     reflectivity: Lumen reflection quality / screen traces / max roughness to trace (post-process overrides on
        the same sources), and transient MIDs on the P02 floor slabs and on wing "Front" slots near the camera with
        every scalar parameter whose name holds "rough" scaled down. Prefer running AFTER p02_floor_walnut.py
        (walnut_policy "warn" logs P02_FOG_BENCH_E_BEFORE_WALNUT, "require" refuses).
  ALL   A+B+C+D+E together.

Modes (BENCH_MODE): PREPARE (editor world, PIE NOT running: spawns the hidden ZZ_P02FOG_MIST_* pool, never
saves), CAPTURE (PIE: the stills run; BENCH_DRY=True only scrubs, settles, plans and shoots base), RESTORE (PIE:
re-applies every original from the run records, hides the pool). The map is dirty after PREPARE by design; the
conductor ends with a Don't-Save editor restart.

Flicker (P02's HUM/BUZZ/FAULT light functions keep running while the Master is paused): the luma gates are
ROBUST. Settle = the medians of the two halves of the last settle_window probes agree; base return = the settled
median is back within max(abs, rel * ref, iqr_k * IQR). A frame matched to the flicker phase is NOT used: the
flicker runs on material time, which the Master frame does not set [inferred: the light-function Time input is
renderer-private and could not be read], so the same Master frame does not give the same flicker phase. Each
shot takes stills_per_shot stills; the contact sheet picks the one nearest the shot's median luma.

Markers carry run ids: P02_FOG_BENCH_START|run=..., P02_FOG_BENCH_ANNOUNCE|run=..., P02_FOG_BENCH_PLAN|run=...,
P02_FOG_BENCH_PREPARE_OK|run=..., P02_FOG_BENCH_CAPTURE_OK|run=... (only after restore verified, census equal,
every still on disk and the manifest read back), P02_FOG_BENCH_RESTORE_OK|run=..., P02_FOG_BENCH_FAILED|run=...|
reason=..., P02_FOG_BENCH_NEEDS_DONT_SAVE_RESTART|run=....

Rules carried from memory and look_bench.py, enforced here: originals READ, WRITTEN (fsync, re-read) before the
first change of each position; no save call anywhere (harness scan); no spawn / destroy in the PIE adapter or the
engine-free classes (harness scan); Unreal objects only inside closures; no exposure override in the captures
except the D variant itself.
"""
from __future__ import annotations

import builtins
import datetime
import json
import math
import os
import pathlib
import re
import time
import traceback

import look_bench as lb
import passage_stills as ps

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
OUT_ROOT = BASE / "P02FogBench"
PREPARE_ROOT = OUT_ROOT / "_prepare"
PREPARE_RECORD_NAME = "p02_fog_bench_prepare.json"
ORIGINALS_NAME = "p02_fog_bench_originals.json"
MANIFEST_NAME = "p02_fog_bench_manifest.json"
OWNER = BASE / "pie_recording_owner.json"
WALNUT_RECORD = BASE / "p02_floor_walnut_record.json"
PREFIX = "ZZ_P02FOG_"
TAG = "ZZ_P02FOG"
HANDLE_NAME = "PUSS_P02_FOG_BENCH_HANDLE"
STATE_NAME = "PUSS_P02_FOG_BENCH_STATE"
MARK = "P02_FOG_BENCH"
RESTART = MARK + "_NEEDS_DONT_SAVE_RESTART"
ORDER = ("base", "A", "B", "C", "D", "E", "ALL")
LABEL_PREFIX = "P02 SCORE"                      # lighting_scores_record_P02.json plan.label_prefix [measured]
LAMP_RE = re.compile(r"^P02 SCORE B(\d{2}) ")
FLOOR_SLABS = ("Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right",
               "Passage 02 - Floor Far")      # p02_floor_walnut.py:21
P01_SLAB = "Passage 01 - Opening Floor"        # p02_floor_walnut.py:24
SKIP_LIGHT_CLASSES = ("InfinityStageSweepLight", "InfinityStageStrobeLight")
PP_EXPOSURE = ("override_auto_exposure_min_brightness", "auto_exposure_min_brightness",
               "override_auto_exposure_max_brightness", "auto_exposure_max_brightness")
PP_READ_ONLY = ("override_auto_exposure_method", "auto_exposure_method")
KINDS = ("light", "fog", "media", "pp", "mid", "cvar")

DEFAULTS = {
    "passage": "P02",
    "bay_count": 23,                 # lighting_scores_record_P02.json plan.bay_count [measured]
    # bay -> Passage fraction (bay - 1) / bay_count unless "fraction" is given. The position gate checks the
    # nearest P02 SCORE bay ahead of the camera.
    "positions": ({"name": "bay08", "bay": 8}, {"name": "bay15", "bay": 15}),
    "position_tol_bays": 2,
    "variants": ORDER,
    "resolution": (1600, 900),       # passage_stills DEFAULTS
    "stills_per_shot": 3,
    "still_gap_s": 0.7,
    "repose_seconds": 1.0,
    "settle_min_seconds": 4.0,
    "settle_max_seconds": 24.0,
    "probe_interval_s": 0.5,
    "probe_timeout_s": 4.0,
    "probe_resolution": (256, 144),
    "settle_window": 6,
    "settle_tol_abs": 3.0,
    "settle_tol_rel": 0.05,
    "base_return_tol_abs": 4.0,
    "base_return_tol_rel": 0.10,
    "base_return_iqr_k": 1.0,
    "frame_tol_ticks": 1,
    "file_min_bytes": 1000,
    "file_stable_ticks": 4,
    "file_timeout_s": 45.0,
    "fov_fallback_deg": 90.0,
    "run_timeout_s": 2400.0,
    "rot_tol_deg": 1e-3,
    "show_strobes": "off",           # "off" = strobe_enabled False for the run (look_bench mechanism), restored
    "sweep_lights": "off",           # the P02 car light floods white (PIE_TEST_LIST_2026-10-05.md:23); restored
    "screen_messages": "off",
    "walnut_policy": "warn",         # "warn" | "require"
    # A
    "a_radius_cm": 6000.0,
    "a_keep_beams": 2,
    "a_beam_tokens": ("BEAM",),
    "a_shaft_probe_cm": 600.0,       # a lamp counts as in view if its location or a point this far down its axis is
    # B
    "b_fog_density_scale": 0.15,
    "b_volumetric": "keep",          # "keep" | "off"
    "b_media": "zero",               # "zero" | "keep": Effect-Source local media near the camera
    "b_media_radius_cm": 8000.0,
    "b_mist_count": 4,
    "b_mist_radius_cm": 1600.0,      # uniform-scale sphere; [inf] GetBaseVolumeSize()=500 read as a RADIUS, as
    "b_mist_first_ahead_cm": 1200.0, # look_bench.py:1559 does; the first live still confirms the band height
    "b_mist_spacing_cm": 2400.0,
    "b_mist_top_cm": 150.0,
    "b_mist_top_fraction": 0.05,
    "b_mist_density": 0.35,          # [inf] look-test value; look_bench haze used 0.04-0.22 radial
    "b_mist_phase_g": 0.4,
    "b_floor_below_camera_cm": 180.0,  # fallback floor z = camera z - this, when no P02 slab is under the camera
    # C
    "c_tokens": ("LOW_SIDE",),
    "c_bays_behind": 1,
    "c_bays_ahead": 4,
    "c_graze_deg": 12.0,
    "c_direction": "forward",        # "forward" = beam travels away from the camera, "back" = toward it (backlight)
    "c_pitch_deg": 2.0,
    "c_dark_pitch_deg": -85.0,
    "c_alternate": True,
    # D
    "d_cal_iters": 7,
    "d_cal_tol_abs": 2.0,
    "d_ev_clamp": (-8.0, 12.0),
    # E
    "e_pp": {"lumen_reflection_quality": 2.0, "lumen_reflections_screen_traces": True,
             "lumen_max_roughness_to_trace_reflections": 0.6},
    "e_cvars": {},                   # optional {"r.Lumen.Reflections.DownsampleFactor": 1} (binary-proven names)
    "e_rough_token": "rough",
    "e_floor_rough_scale": 0.35,
    "e_wing_slot": "Front",          # Flat V3 slots Front/Flap/Timber/Edge (AGENTS.md, FlatV3Spec)
    "e_wing_rough_scale": 0.6,
    "e_wing_radius_cm": 4000.0,
    "e_wing_max_components": 64,
}
E_PP_OVERRIDE = {"lumen_reflection_quality": "override_lumen_reflection_quality",
                 "lumen_reflections_screen_traces": "override_lumen_reflections_screen_traces",
                 "lumen_max_roughness_to_trace_reflections": "override_lumen_max_roughness_to_trace_reflections"}


class BenchRefused(RuntimeError):
    def __init__(self, reason, detail="", run="?"):
        self.reason, self.detail = reason, str(detail)
        super().__init__("%s_FAILED|run=%s|reason=%s%s" % (MARK, run, reason, ("|" + self.detail) if detail else ""))


# --------------------------------------------------------------------------
# pure helpers (no Unreal): tested offline by test_p02_fog_bench.py
# --------------------------------------------------------------------------

def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def key(kind, oid, field):
    if kind not in KINDS:
        raise ValueError("%s_BAD_KIND|%s" % (MARK, kind))
    return "%s|%s|%s" % (kind, oid, field)


def split_key(k):
    kind, rest = k.split("|", 1)
    oid, field = rest.rsplit("|", 1)
    return kind, oid, field


def op(kind, oid, field, value):
    return (kind, oid, field, value)


def plain(v):
    if isinstance(v, (tuple, list)):
        return [plain(x) for x in v]
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    return v


def ang(a, b):
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def same_value(field, a, b, tol_deg):
    """Equality used by verify / hold: rotations within tol_deg per axis (rotator -> quat -> rotator round trip);
    numbers within float32 storage precision (a Python 0.6 reads back from a float UPROPERTY as 0.6000000238);
    everything else (bools, enums, material paths) exact."""
    if field == "rotation":
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        return all(ang(a[k], b[k]) <= tol_deg for k in ("roll", "pitch", "yaw"))
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    num = lambda v: isinstance(v, (int, float))
    if num(a) and num(b):
        return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(a)), abs(float(b)))
    return plain(a) == plain(b)


def stats(values):
    v = sorted(float(x) for x in values)
    if not v:
        return None

    def q(f):
        pos = f * (len(v) - 1)
        lo = int(math.floor(pos))
        hi = min(len(v) - 1, lo + 1)
        return v[lo] + (v[hi] - v[lo]) * (pos - lo)
    return {"n": len(v), "median": q(0.5), "p10": q(0.1), "p25": q(0.25), "p75": q(0.75), "p90": q(0.9),
            "iqr": q(0.75) - q(0.25), "min": v[0], "max": v[-1]}


def robust_settle(samples, elapsed, p):
    """'stable' when the medians of the two halves of the last settle_window probes agree within
    max(settle_tol_abs, settle_tol_rel * median) and elapsed >= settle_min_seconds; 'timeout' past
    settle_max_seconds; else 'wait'. A stationary flicker passes; a picture still adapting does not."""
    w = int(p["settle_window"])
    vals = [float(s[1]) for s in samples]
    if len(vals) >= w and elapsed >= float(p["settle_min_seconds"]):
        last = vals[-w:]
        a = stats(last[:w // 2])["median"]
        b = stats(last[w // 2:])["median"]
        mid = stats(last)["median"]
        if abs(a - b) <= max(float(p["settle_tol_abs"]), float(p["settle_tol_rel"]) * mid):
            return "stable"
    if elapsed > float(p["settle_max_seconds"]):
        return "timeout"
    return "wait"


def base_return_ok(now, ref, p):
    """now / ref: stats() of the settle windows. Flicker-tolerant: the IQR widens the tolerance."""
    tol = max(float(p["base_return_tol_abs"]), float(p["base_return_tol_rel"]) * float(ref["median"]),
              float(p["base_return_iqr_k"]) * max(float(ref["iqr"]), float(now["iqr"])))
    return abs(float(now["median"]) - float(ref["median"])) <= tol, tol


def bisect_ev(lo, hi, ev, luma, target):
    """Higher locked EV = darker picture. Too bright -> raise the floor of the interval."""
    return (ev, hi) if float(luma) > float(target) else (lo, ev)


def lamp_bay(label):
    m = LAMP_RE.match(str(label or ""))
    return int(m.group(1)) if m else None


def route_axes(pose):
    yaw = math.radians(float(pose["rot"]["yaw"]))
    return (math.cos(yaw), math.sin(yaw)), (-math.sin(yaw), math.cos(yaw))


def along_lateral(pose, loc):
    fwd, right = route_axes(pose)
    dx, dy = loc[0] - pose["loc"][0], loc[1] - pose["loc"][1]
    return dx * fwd[0] + dy * fwd[1], dx * right[0] + dy * right[1]


def dist3(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def forward_of(rot):
    return lb.rotator_axes(rot["yaw"], rot["pitch"], rot["roll"])[0]


def nearest_bay_ahead(lights, pose, behind_cm=300.0):
    cent = {}
    for l in lights:
        b = lamp_bay(l["label"])
        if b is not None:
            cent.setdefault(b, []).append(l["location"])
    best = None
    for b, pts in cent.items():
        c = lb.centroid(pts)
        along, _lat = along_lateral(pose, c)
        if along >= -behind_cm and (best is None or along < best[1]):
            best = (b, along)
    return best[0] if best else None


def position_rows(start, end, positions, p):
    rows = []
    for i, pos in enumerate(positions):
        frac = pos.get("fraction")
        if frac is None:
            frac = (int(pos["bay"]) - 1) / float(p["bay_count"])
        rows.append({"i": i, "name": str(pos["name"]), "bay": int(pos["bay"]), "fraction": float(frac),
                     "target_frame": ps.fraction_to_frame(start, end, frac)})
    if len({r["target_frame"] for r in rows}) != len(rows) or len({r["name"] for r in rows}) != len(rows):
        raise BenchRefused("positions_collide")
    return rows


def in_view_any(pose, pts):
    return any(lb.in_view(pose, tuple(pt)) for pt in pts)


def plan_a(lights, pose, p):
    near = [l for l in lights if dist3(l["location"], pose["loc"]) <= float(p["a_radius_cm"])]
    beams = []
    for l in near:
        if any(t in l["label"] for t in p["a_beam_tokens"]):
            fwd = forward_of(l["rotation"])
            probe = [l["location"][i] + fwd[i] * float(p["a_shaft_probe_cm"]) for i in range(3)]
            if in_view_any(pose, (l["location"], probe)):
                beams.append(l)
    keep = sorted(beams, key=lambda l: (dist3(l["location"], pose["loc"]), l["label"]))[:int(p["a_keep_beams"])]
    keep_ids = {l["id"] for l in keep}
    ops = [op("light", l["id"], "volumetric_scattering_intensity", 0.0)
           for l in sorted(near, key=lambda l: l["id"]) if l["id"] not in keep_ids]
    return {"ops": ops, "pool": [], "info": {"kept_beams": [l["label"] for l in keep], "zeroed": len(ops),
                                             "near": len(near), "no_beam_in_view": not keep}}


def mist_specs(pose, floor_z, p):
    fwd, _right = route_axes(pose)
    r = float(p["b_mist_radius_cm"])
    # unit-sphere height of the band top, density exp(-F * z_unit) (VolumetricFog.usf:234) -> F
    falloff = math.log(1.0 / float(p["b_mist_top_fraction"])) / (float(p["b_mist_top_cm"]) / r)
    out = []
    for i in range(int(p["b_mist_count"])):
        d = float(p["b_mist_first_ahead_cm"]) + i * float(p["b_mist_spacing_cm"])
        out.append({"label": PREFIX + "MIST_%d" % i, "kind": "fog",
                    "loc": (pose["loc"][0] + fwd[0] * d, pose["loc"][1] + fwd[1] * d, float(floor_z)),
                    "yaw": float(pose["rot"]["yaw"]), "scale": r / 500.0, "radial": 0.0,
                    "height": float(p["b_mist_density"]), "falloff": falloff, "offset": 0.0,
                    "phase_g": float(p["b_mist_phase_g"])})
    return out


def plan_b(fogs, media, pose, floor_z, p):
    ops = []
    k = float(p["b_fog_density_scale"])
    for f in sorted(fogs, key=lambda f: f["id"]):
        ops.append(op("fog", f["id"], "fog_density", float(f["fog_density"]) * k))
        ops.append(op("fog", f["id"], "second_fog_density", float(f["second_fog_density"]) * k))
        if p["b_volumetric"] == "off":
            ops.append(op("fog", f["id"], "volumetric_fog", False))
    zeroed = []
    if p["b_media"] == "zero":
        for m in sorted(media, key=lambda m: m["id"]):
            if dist3(m["location"], pose["loc"]) <= float(p["b_media_radius_cm"]):
                ops.append(op("media", m["id"], "radial_fog_extinction", 0.0))
                ops.append(op("media", m["id"], "height_fog_extinction", 0.0))
                zeroed.append(m["label"])
    pool = mist_specs(pose, floor_z, p)
    return {"ops": ops, "pool": pool, "info": {"fogs": len(fogs), "media_zeroed": zeroed, "mist": len(pool),
                                               "floor_z": float(floor_z), "volumetric": p["b_volumetric"],
                                               "mist_falloff": pool[0]["falloff"] if pool else None}}


def graze_rotation(pose, loc, p):
    fwd, right = route_axes(pose)
    _along, lat = along_lateral(pose, loc)
    side = 1.0 if lat >= 0.0 else -1.0
    sgn = -1.0 if p["c_direction"] == "back" else 1.0
    g = math.radians(float(p["c_graze_deg"]))
    d = (sgn * fwd[0] * math.cos(g) + side * right[0] * math.sin(g),
         sgn * fwd[1] * math.cos(g) + side * right[1] * math.sin(g))
    return {"roll": 0.0, "pitch": float(p["c_pitch_deg"]), "yaw": math.degrees(math.atan2(d[1], d[0]))}


def plan_c(lights, pose, bay, p):
    lo, hi = int(bay) - int(p["c_bays_behind"]), int(bay) + int(p["c_bays_ahead"])
    ops, lit, dark = [], [], []
    for l in sorted(lights, key=lambda l: l["id"]):
        b = lamp_bay(l["label"])
        if b is None or not (lo <= b <= hi) or not any(t in l["label"] for t in p["c_tokens"]):
            continue
        is_lit = (not p["c_alternate"]) or ((b - lo) % 2 == 0)
        if is_lit:
            rot = graze_rotation(pose, l["location"], p)
            lit.append(l["label"])
        else:
            rot = {"roll": 0.0, "pitch": float(p["c_dark_pitch_deg"]), "yaw": float(l["rotation"]["yaw"])}
            dark.append(l["label"])
        ops.append(op("light", l["id"], "rotation", rot))
    return {"ops": ops, "pool": [], "info": {"lit": lit, "dark": dark, "bays": [lo, hi], "noop": not ops}}


def affecting(sources):
    return [s for s in sources if s.get("affects")]


def effective_exposure(sources):
    """Approximate effective exposure: affecting sources in blend order (volumes by priority, then the camera),
    the last one that overrides a field wins. Blend weights < 1 are not modelled (logged)."""
    order = sorted(affecting(sources), key=lambda s: (s["kind"] == "camera", float(s.get("priority", 0.0))))
    out = {"method": None, "min": None, "max": None, "partial_weights": []}
    for s in order:
        f = s["fields"]
        if f.get("override_auto_exposure_method"):
            out["method"] = str(f.get("auto_exposure_method"))
        if f.get("override_auto_exposure_min_brightness"):
            out["min"] = float(f["auto_exposure_min_brightness"])
        if f.get("override_auto_exposure_max_brightness"):
            out["max"] = float(f["auto_exposure_max_brightness"])
        if float(s.get("weight", 1.0)) < 1.0:
            out["partial_weights"].append(s["id"])
    out["locked"] = out["min"] is not None and out["min"] == out["max"]
    out["manual"] = "MANUAL" in str(out["method"] or "").upper()
    return out


def plan_d(sources, ev):
    ops = []
    for s in sorted(affecting(sources), key=lambda s: s["id"]):
        ops += [op("pp", s["id"], "override_auto_exposure_min_brightness", True),
                op("pp", s["id"], "auto_exposure_min_brightness", float(ev)),
                op("pp", s["id"], "override_auto_exposure_max_brightness", True),
                op("pp", s["id"], "auto_exposure_max_brightness", float(ev))]
    return ops


def mid_spec(row, scalars, token, scale):
    hit = {n: float(v) * float(scale) for n, v in sorted(scalars.items()) if token in n.lower()}
    return {"mid_parent": row["material"], "scalars": hit} if hit else None


def plan_e(sources, floor_slots, wing_slots, scalars_of, p):
    ops = []
    for s in sorted(affecting(sources), key=lambda s: s["id"]):
        for field, value in sorted(p["e_pp"].items()):
            ops.append(op("pp", s["id"], E_PP_OVERRIDE[field], True))
            ops.append(op("pp", s["id"], field, value))
    for name, value in sorted(p["e_cvars"].items()):
        ops.append(op("cvar", name, "value", value))
    floor_hit, floor_noop, wing_hit, wing_noop = [], [], [], []
    for rows, scale, hit, noop in ((floor_slots, p["e_floor_rough_scale"], floor_hit, floor_noop),
                                   (wing_slots, p["e_wing_rough_scale"], wing_hit, wing_noop)):
        for row in sorted(rows, key=lambda r: (r["id"], r["slot"])):
            spec = mid_spec(row, scalars_of.get(row["material"], {}), p["e_rough_token"], scale) \
                if row["material"] else None
            if spec is None:
                noop.append("%s[%d]" % (row["id"], row["slot"]))
                continue
            ops.append(op("mid", row["id"], "slot%d" % row["slot"], spec))
            hit.append("%s[%d]" % (row["id"], row["slot"]))
    return {"ops": ops, "pool": [], "info": {"pp_sources": len(affecting(sources)), "floor_mids": len(floor_hit),
                                             "floor_noop": floor_noop, "wing_mids": len(wing_hit),
                                             "wing_noop": len(wing_noop)}}


def variant_plan(name, plans, ev):
    """plans: {"A": plan_a(), "B": ..., "C": ..., "E": ..., "D_sources": pp sources}. -> (ops, pool specs)."""
    parts = {"base": (), "A": ("A",), "B": ("B",), "C": ("C",), "D": ("D",), "E": ("E",),
             "ALL": ("A", "B", "C", "D", "E")}[name]
    ops, pool = [], []
    for part in parts:
        if part == "D":
            ops += plan_d(plans["D_sources"], ev) if ev is not None else []
        else:
            ops += plans[part]["ops"]
            pool += plans[part]["pool"]
    seen = {}
    for o in ops:
        k = key(o[0], o[1], o[2])
        if k in seen and plain(seen[k]) != plain(o[3]):
            raise RuntimeError("%s_CONFLICT|%s|%s" % (MARK, name, k))
        seen[k] = o[3]
    return ops, pool


def all_keys(plans, positions_ev=0.0):
    keys = set()
    for name in ORDER:
        ops, _pool = variant_plan(name, plans, positions_ev)
        keys.update(key(o[0], o[1], o[2]) for o in ops)
    return sorted(keys)


def position_tasks(variants, d_needed, dry=False):
    """The task list for one position: base first, D calibration after the base shot, a base return before every
    variant that follows a change (and after the last), never two applies without a base return between."""
    tasks = [("jump",), ("repose",), ("settle", "base_ref"), ("plan",), ("shoot", "base")]
    if dry:
        return tasks
    changed = False
    if d_needed and any(v in ("D", "ALL") for v in variants):
        tasks.append(("dcal",))
        changed = True
    for v in variants:
        if v == "base":
            continue
        if changed:
            tasks.append(("settle", "base_return"))
        tasks += [("apply", v), ("settle", "state"), ("hold", v), ("shoot", v)]
        changed = True
    if changed:
        tasks.append(("settle", "base_return_final"))
    return tasks


def write_verified(path, data, log=None, run="?"):
    path = pathlib.Path(path)
    text = json.dumps(plain(data), indent=1, sort_keys=True, default=str)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    if json.loads(path.read_text(encoding="utf-8")) != json.loads(text):
        raise RuntimeError("%s_RECORD_READBACK|%s" % (MARK, path.as_posix()))
    if log:
        log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, path.as_posix()))
    return path


def walnut_state(floor_mats, p01_mats, record_exists):
    """Walnut is applied when every P02 slab slot renders P01's slab material (p02_floor_walnut.py sets that)."""
    p01 = set(m for m in p01_mats if m)
    applied = bool(floor_mats) and bool(p01) and all(m in p01 for m in floor_mats)
    return {"applied": applied, "record_exists": bool(record_exists), "p02": sorted(set(map(str, floor_mats))),
            "p01": sorted(p01)}


# --------------------------------------------------------------------------
# engine-free bench: originals, apply, hold, restore, verify (adapter injected)
# --------------------------------------------------------------------------

class FogBench:
    """Never spawns or destroys: it changes properties of existing PIE actors / components and places, shows
    and hides the PREPAREd ZZ_P02FOG_ pool."""

    def __init__(self, adapter, record_path, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or ("P02FOG-" + utc_stamp())
        self.record = None
        self.applied = None

    def write(self):
        write_verified(self.record_path, self.record, self.a.log, self.run_id)
        self.a.note("record_written")

    def read_globals(self, census, prepare):
        strobes = self.a.show_strobes() if self.p["show_strobes"] == "off" else []
        sweeps = self.a.sweep_lights() if self.p["sweep_lights"] == "off" else []
        self.record = {"run": self.run_id, "written_utc": utc_iso(), "world": self.a.world_name(),
                       "params": plain(self.p), "census_before": census, "show_strobes": strobes,
                       "sweep_lights": sweeps, "originals": {}, "pool_labels": sorted(self.a.pool_labels()),
                       "prepare_run": (prepare or {}).get("run"), "positions": {}, "status": "armed"}
        self.write()
        return self.record

    def record_keys(self, keys, position=None, plan_summary=None):
        """Originals of every key are on disk before the first change that touches it (first-seen wins)."""
        new = [k for k in keys if k not in self.record["originals"]]
        for k in new:
            self.record["originals"][k] = plain(self.a.read(*split_key(k)))
        if position is not None:
            self.record["positions"][position] = plain(plan_summary or {})
        if new or position is not None:
            self.write()
        return len(new)

    def neutralise(self):
        n = 0
        for row in self.record["show_strobes"]:
            if row["enabled"]:
                self.a.set_show_strobe(row["id"], False)
                n += 1
        for row in self.record["sweep_lights"]:
            if row["enabled"]:
                self.a.set_sweep(row["id"], False)
                n += 1
        bad = [r["label"] for r in self.record["show_strobes"] if self.a.show_strobe_enabled(r["id"])] + \
              [r["label"] for r in self.record["sweep_lights"] if self.a.sweep_enabled(r["id"])]
        if bad:
            raise RuntimeError("%s_NEUTRALISE_FAILED|%s" % (MARK, ",".join(bad)))
        self.a.log("%s_SHOW_LIGHTS_OFF|run=%s|strobes=%d|sweeps=%d|disabled=%d" % (
            MARK, self.run_id, len(self.record["show_strobes"]), len(self.record["sweep_lights"]), n))
        return n

    def to_base(self):
        tol = float(self.p["rot_tol_deg"])
        for k, orig in self.record["originals"].items():
            kind, oid, field = split_key(k)
            if not same_value(field, self.a.read(kind, oid, field), orig, tol):
                self.a.write(kind, oid, field, orig)
        for label in self.a.pool_labels():
            if self.a.pool_state(label)["on"]:
                self.a.hide_pool(label)
        self.applied = None

    def apply(self, name, ops, pool_specs):
        if self.record is None or not self.record_path.is_file():
            raise RuntimeError("%s_NO_RECORD|originals must be on disk before any change" % MARK)
        missing = [key(o[0], o[1], o[2]) for o in ops if key(o[0], o[1], o[2]) not in self.record["originals"]]
        if missing:
            raise RuntimeError("%s_NOT_RECORDED|%d|%s" % (MARK, len(missing), ",".join(missing[:4])))
        pool = set(self.a.pool_labels())
        lost = [s["label"] for s in pool_specs if s["label"] not in pool]
        if lost:
            raise RuntimeError("%s_POOL_MISSING|%s" % (MARK, ",".join(lost)))
        self.to_base()
        for kind, oid, field, value in ops:
            self.a.write(kind, oid, field, value)
        for spec in pool_specs:
            self.a.show_pool(spec)
        self.applied = (name, list(ops), list(pool_specs))
        self.a.log("%s_STATE|run=%s|variant=%s|ops=%d|pool=%d" % (MARK, self.run_id, name, len(ops), len(pool_specs)))

    def held(self):
        """After the settle: is every applied value still in place (Light Drama slow-move, a Sequencer key, an
        effect re-apply would overwrite one)? MIDs: the slot must no longer hold the original material."""
        if not self.applied:
            return []
        out = []
        tol = float(self.p["rot_tol_deg"])
        for kind, oid, field, value in self.applied[1]:
            now = self.a.read(kind, oid, field)
            k = key(kind, oid, field)
            if kind == "mid":
                if now == self.record["originals"][k]:
                    out.append(k)
            elif not same_value(field, now, value, tol):
                out.append(k)
        for spec in self.applied[2]:
            if not self.a.pool_state(spec["label"])["on"]:
                out.append("pool|" + spec["label"])
        return out

    def restore(self):
        self.to_base()
        for row in self.record.get("show_strobes", []):
            if self.a.show_strobe_enabled(row["id"]) != row["enabled"]:
                self.a.set_show_strobe(row["id"], row["enabled"])
        for row in self.record.get("sweep_lights", []):
            if self.a.sweep_enabled(row["id"]) != row["enabled"]:
                self.a.set_sweep(row["id"], row["enabled"])
        return self.verify()

    def verify(self):
        problems = []
        tol = float(self.p["rot_tol_deg"])
        for k, orig in self.record["originals"].items():
            kind, oid, field = split_key(k)
            now = self.a.read(kind, oid, field)
            if not same_value(field, now, orig, tol):
                problems.append("%s %r != %r" % (k, now, orig))
        lit = [l for l in self.a.pool_labels() if self.a.pool_state(l)["on"]]
        if lit:
            problems.append("pool still shown %s" % ",".join(sorted(lit)))
        for row in self.record.get("show_strobes", []):
            if self.a.show_strobe_enabled(row["id"]) != row["enabled"]:
                problems.append("show strobe %s != %r" % (row["label"], row["enabled"]))
        for row in self.record.get("sweep_lights", []):
            if self.a.sweep_enabled(row["id"]) != row["enabled"]:
                problems.append("sweep light %s != %r" % (row["label"], row["enabled"]))
        return problems


def restore_from_record(adapter, record_path):
    record = json.loads(pathlib.Path(record_path).read_text(encoding="utf-8"))
    bench = FogBench(adapter, record_path, record.get("params"), record.get("run"))
    bench.record = record
    return bench.restore()


def restore_all(adapter, records, log):
    """Newest record first, so the OLDEST originals are written last."""
    problems = []
    for path in sorted((pathlib.Path(r) for r in records), key=lambda r: r.as_posix(), reverse=True):
        got = restore_from_record(adapter, path)
        log("%s_RESTORED_RECORD|%s|problems=%d" % (MARK, path.as_posix(), len(got)))
        problems += got
    for label in adapter.pool_labels():
        if adapter.pool_state(label)["on"]:
            adapter.hide_pool(label)
    lit = [l for l in adapter.pool_labels() if adapter.pool_state(l)["on"]]
    if lit:
        problems.append("pool still shown %s" % ",".join(sorted(lit)))
    return problems


# --------------------------------------------------------------------------
# PREPARE (editor world, PIE not running): the hidden ZZ_P02FOG_MIST_* pool
# --------------------------------------------------------------------------

def pool_labels_needed(p):
    return [PREFIX + "MIST_%d" % i for i in range(int(p["b_mist_count"]))]


class PrepareBench:
    def __init__(self, adapter, record_path, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or ("P02FOGPREP-" + utc_stamp())
        self.record = None

    def run(self):
        kind = self.a.world_kind()
        if kind != "editor":
            raise BenchRefused("prepare_needs_editor", "world=%s; end PIE first" % kind, self.run_id)
        census = self.a.census()
        if census["maps"] or census["content"]:
            raise BenchRefused("dirty_before_prepare", json.dumps(census), self.run_id)
        left = self.a.bench_actor_labels(PREFIX)
        if left:
            raise BenchRefused("leftovers", "%d %s* actors; Don't-Save restart first" % (len(left), PREFIX),
                               self.run_id)
        labels = pool_labels_needed(self.p)
        self.record = {"run": self.run_id, "written_utc": utc_iso(), "world": self.a.world_name(),
                       "census_before": census, "tag": TAG, "prefix": PREFIX, "pool": labels, "spawned": {},
                       "status": "planned", "params": plain(self.p)}
        write_verified(self.record_path, self.record, self.a.log, self.run_id)
        self.a.note("record_written")
        self.a.log("%s_ANNOUNCE|run=%s|world=EDITOR|spawning %d hidden %s* Local Fog Volumes (tag %s); they stay until "
                   "a Don't-Save restart; the map WILL be dirty and must NOT be saved|record=%s" % (
                       MARK, self.run_id, len(labels), PREFIX, TAG, self.record_path.as_posix()))
        complete = False
        try:
            for label in labels:
                self.record["spawned"][label] = self.a.spawn_hidden({"label": label, "kind": "fog"})
            complete = True
        finally:
            after = self.a.census()
            self.record.update(status="spawned" if complete else "partial", census_after=after,
                               dirtied_by_prepare={"maps": sorted(set(after["maps"]) - set(census["maps"])),
                                                   "content": sorted(set(after["content"]) - set(census["content"]))})
            write_verified(self.record_path, self.record, self.a.log, self.run_id)
            self.a.log("%s|run=%s|editor world holds %s* actors and a dirty map; Don't-Save restart, never Save All"
                       % (RESTART, self.run_id, PREFIX))
        present = set(self.a.pool_labels())
        problems = []
        if present != set(labels):
            problems.append("pool mismatch missing=%s extra=%s" % (sorted(set(labels) - present),
                                                                  sorted(present - set(labels))))
        problems += ["%s not hidden" % l for l in labels if l in present and self.a.pool_state(l)["on"]]
        if problems:
            raise BenchRefused("prepare_verify", ";".join(problems), self.run_id)
        self.a.log("%s_PREPARE_OK|run=%s|actors=%d|record=%s" % (MARK, self.run_id, len(labels),
                                                                  self.record_path.as_posix()))
        return self.record


def find_prepare_record(root=PREPARE_ROOT, explicit=None):
    if explicit:
        path = pathlib.Path(explicit)
        if not path.is_file():
            raise BenchRefused("not_prepared", "no record at %s" % path.as_posix())
        return path
    found = sorted(pathlib.Path(root).glob("*/" + PREPARE_RECORD_NAME))
    if not found:
        raise BenchRefused("not_prepared", "run PREPARE in the editor world (PIE not running) first")
    return found[-1]


def load_prepare_record(path):
    rec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if rec.get("status") != "spawned":
        raise BenchRefused("prepare_incomplete", "status=%s" % rec.get("status"))
    return rec


# --------------------------------------------------------------------------
# CAPTURE state machine (engine-free; Slate tick in the editor, fake clock in the harness)
# --------------------------------------------------------------------------

class FogMachine:
    def __init__(self, bench, adapter, run, luma_reader=None):
        self.b, self.a, self.p, self.run = bench, adapter, bench.p, run
        self.read_luma = luma_reader or lb.png_luma
        self.pos_i = 0
        self.queue = []
        self.task = None
        self.sub = {}
        self.st = {"gate_failures": [], "probe_n": 0, "probe_timeouts": 0, "task_log": []}
        self.done = False
        self.pos = None
        self._start_position()

    # ---- helpers
    def _fail(self, why):
        self.st["gate_failures"].append(why)
        if self.pos is not None:
            self.pos.setdefault("gate_failures", []).append(why)
        self.a.log("%s_GATE|run=%s|%s" % (MARK, self.b.run_id, why))

    def _start_position(self):
        if self.pos_i >= len(self.run["positions"]):
            self.done = True
            return
        self.pos = self.run["positions"][self.pos_i]
        self.pos.update(shots={}, settles=[], base_returns=[], dcal=None, gate_failures=[])
        self.queue = list(position_tasks(self.p["variants"], True, self.run.get("dry")))
        self.task = None

    def _scrub(self):
        res = self.a.transport_scrub(self.pos["target_frame"])
        self.pos.setdefault("scrub_results", []).append(str(res))
        if not ps.scrub_ok(res):
            raise BenchRefused("scrub_refused", "%s frame=%d result=%s" % (self.pos["name"], self.pos["target_frame"],
                                                                           res), self.b.run_id)

    def _probe(self, now, tag):
        sub = self.sub
        pend = sub.get("pending")
        if pend:
            try:
                y = float(self.read_luma(pend["path"]))
            except Exception:                      # HighResShot writes asynchronously: retry next tick
                if now - pend["t"] > float(self.p["probe_timeout_s"]):
                    self.st["probe_timeouts"] += 1
                    sub["pending"] = None
                return
            sub["samples"].append([round(now - sub["t0"], 3), round(y, 3)])
            sub["pending"] = None
            return
        if sub.get("last_issue") is None or now - sub["last_issue"] >= float(self.p["probe_interval_s"]):
            d = pathlib.Path(self.run["run_dir"]) / "_probes"
            d.mkdir(parents=True, exist_ok=True)
            self.st["probe_n"] += 1
            path = (d / ("%s_%s_%04d.png" % (self.pos["name"], tag, self.st["probe_n"]))).as_posix()
            w, h = self.p["probe_resolution"]
            self.a.console('HighResShot %dx%d filename="%s"' % (w, h, path))
            sub["pending"] = {"path": path, "t": now}
            sub["last_issue"] = now

    def _next_task(self, now):
        if not self.queue:
            self.pos_i += 1
            self._start_position()
            return
        self.task = self.queue.pop(0)
        self.sub = {"t0": now, "begun": False}
        self.st["task_log"].append([self.pos["name"]] + list(self.task))

    def _variant_ops(self, name):
        return variant_plan(name, self.pos["_plans"], self.pos.get("ev"))

    # ---- the step
    def step(self, now):
        if self.done:
            return
        if self.a.world_kind() != "game":
            raise BenchRefused("pie_ended", "PIE world gone mid-run", self.b.run_id)
        if self.task is None:
            self._next_task(now)
            if self.done or self.task is None:
                return
        t = self.task
        kind = t[0]
        sub = self.sub
        if kind == "jump":
            self.a.transport_pause()
            self._scrub()
            self.task = None
            return
        if kind == "repose":
            if now - sub["t0"] >= float(self.p["repose_seconds"]):
                self._scrub()
                self.task = None
            return
        if kind == "settle":
            if not sub["begun"]:
                if t[1].startswith("base_return"):
                    self.b.to_base()
                sub.update(begun=True, t0=now, samples=[], pending=None, last_issue=None)
                return
            self._probe(now, t[1])
            el = now - sub["t0"]
            verdict = robust_settle(sub["samples"], el, self.p)
            if verdict == "wait":
                return
            w = int(self.p["settle_window"])
            st_now = stats([s[1] for s in sub["samples"][-w:]]) if sub["samples"] else None
            rec = {"kind": t[1], "verdict": verdict, "seconds": round(el, 3), "stats": st_now,
                   "after": self.pos.get("_last_variant", "base"), "samples": sub["samples"]}
            self.pos["settles"].append(rec)
            self.a.log("%s_SETTLE|run=%s|pos=%s|kind=%s|verdict=%s|median=%s|iqr=%s|seconds=%.1f" % (
                MARK, self.b.run_id, self.pos["name"], t[1], verdict,
                "%.1f" % st_now["median"] if st_now else "none", "%.1f" % st_now["iqr"] if st_now else "none", el))
            if verdict != "stable":
                self._fail("settle %s/%s/%s" % (self.pos["name"], t[1], rec["after"]))
            if t[1] == "base_ref":
                self.pos["base_ref"] = st_now
            elif t[1].startswith("base_return") and st_now and self.pos.get("base_ref"):
                ok, tol = base_return_ok(st_now, self.pos["base_ref"], self.p)
                self.pos["base_returns"].append({"after": rec["after"], "median": st_now["median"],
                                                 "ref": self.pos["base_ref"]["median"], "tol": tol, "ok": ok})
                self.a.log("%s_BASE_RETURN|run=%s|pos=%s|after=%s|median=%.1f|ref=%.1f|tol=%.1f|ok=%s" % (
                    MARK, self.b.run_id, self.pos["name"], rec["after"], st_now["median"],
                    self.pos["base_ref"]["median"], tol, ok))
                if not ok:
                    self._fail("base_return %s after %s %.1f vs %.1f" % (self.pos["name"], rec["after"],
                                                                          st_now["median"],
                                                                          self.pos["base_ref"]["median"]))
            elif t[1] == "dcal":
                self.pos["_dcal_last"] = st_now
            self.task = None
            return
        if kind == "plan":
            self._plan()
            self.task = None
            return
        if kind == "dcal":
            self._dcal_begin()
            self.task = None
            return
        if kind == "dcal_step":
            d = self.pos["dcal"]
            ev = (d["lo"] + d["hi"]) / 2.0
            d["trial"] = ev
            self.b.apply("Dcal", plan_d(self.pos["_plans"]["D_sources"], ev), [])
            self.pos["_last_variant"] = "Dcal"
            self.queue[0:0] = [("settle", "dcal"), ("dcal_eval",)]
            self.task = None
            return
        if kind == "dcal_eval":
            self._dcal_eval()
            self.task = None
            return
        if kind == "apply":
            ops, pool = self._variant_ops(t[1])
            self.b.apply(t[1], ops, pool)
            self.pos["_last_variant"] = t[1]
            self.task = None
            return
        if kind == "hold":
            bad = self.b.held()
            self.pos.setdefault("held", {})[t[1]] = bad
            self.a.log("%s_HELD|run=%s|pos=%s|variant=%s|ok=%s|overwritten=%d%s" % (
                MARK, self.b.run_id, self.pos["name"], t[1], not bad, len(bad),
                ("|" + ",".join(bad[:4])) if bad else ""))
            if bad:
                self._fail("held %s/%s %d overwritten" % (self.pos["name"], t[1], len(bad)))
            self.task = None
            return
        if kind == "shoot":
            self._shoot(now, t[1])
            return
        raise RuntimeError("%s_BAD_TASK|%r" % (MARK, t))

    def _plan(self):
        a, p, pos = self.a, self.p, self.pos
        w, h = p["resolution"]
        pose = a.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
        if pose is None:
            raise BenchRefused("no_camera", "no player camera manager in PIE", self.b.run_id)
        lights = a.lights()
        nearest = nearest_bay_ahead(lights, pose)
        pos.update(pose=pose, nearest_bay=nearest)
        a.log("%s_POSITION|run=%s|pos=%s|target_bay=%d|nearest_bay=%s|frame=%d|cam=%.0f,%.0f,%.0f|yaw=%.1f" % (
            MARK, self.b.run_id, pos["name"], pos["bay"], nearest, a.transport_frame(), pose["loc"][0],
            pose["loc"][1], pose["loc"][2], pose["rot"]["yaw"]))
        if nearest is None or abs(nearest - pos["bay"]) > int(p["position_tol_bays"]):
            self._fail("position %s nearest_bay=%s target=%d" % (pos["name"], nearest, pos["bay"]))
        floor_z = a.floor_top_z(pose["loc"])
        if floor_z is None:
            floor_z = pose["loc"][2] - float(p["b_floor_below_camera_cm"])
        sources = a.pp_sources(pose["loc"])
        floor_slots = a.floor_slots()
        wing_slots = a.wing_slots(pose, float(p["e_wing_radius_cm"]), p["e_wing_slot"])
        if len(wing_slots) > int(p["e_wing_max_components"]):
            a.log("%s_E_WING_CAP|run=%s|pos=%s|found=%d|max=%d|wing MIDs skipped" % (
                MARK, self.b.run_id, pos["name"], len(wing_slots), int(p["e_wing_max_components"])))
            wing_slots = []
        scalars_of = {}
        for row in floor_slots + wing_slots:
            if row["material"] and row["material"] not in scalars_of:
                scalars_of[row["material"]] = a.scalar_params(row["material"])
        plans = {"A": plan_a(lights, pose, p), "B": plan_b(a.fogs(), a.media(), pose, floor_z, p),
                 "C": plan_c(lights, pose, pos["bay"], p), "E": plan_e(sources, floor_slots, wing_slots, scalars_of, p),
                 "D_sources": sources}
        expo = effective_exposure(sources)
        plans["D_info"] = expo
        pos["_plans"] = plans
        summary = {v: plans[v]["info"] for v in ("A", "B", "C", "E")}
        summary["D"] = dict(expo, sources=[s["id"] for s in affecting(sources)])
        summary["walnut"] = self.run.get("walnut")
        summary.update(pose=pose, nearest_bay=nearest, floor_z=floor_z)
        if self.run.get("dry"):
            self.b.record_keys([], pos["name"], summary)
        else:
            self.b.record_keys(all_keys(plans), pos["name"], summary)   # originals on disk BEFORE this position's
        pos["plan"] = summary                                            # first change
        for v in ("A", "B", "C", "E"):
            a.log("%s_PLAN|run=%s|pos=%s|variant=%s|ops=%d|pool=%d|info=%s" % (
                MARK, self.b.run_id, pos["name"], v, len(plans[v]["ops"]), len(plans[v]["pool"]),
                json.dumps(plain(plans[v]["info"]), sort_keys=True)[:400]))
        a.log("%s_PLAN|run=%s|pos=%s|variant=D|sources=%d|method=%s|min=%s|max=%s|locked=%s|manual=%s" % (
            MARK, self.b.run_id, pos["name"], len(affecting(sources)), expo["method"], expo["min"], expo["max"],
            expo["locked"], expo["manual"]))
        if plans["A"]["info"]["no_beam_in_view"]:
            a.log("%s_A_NO_BEAM_IN_VIEW|run=%s|pos=%s|A zeroes every lamp; no shaft is kept" % (
                MARK, self.b.run_id, pos["name"]))
        if plans["C"]["info"]["noop"]:
            a.log("%s_C_NOOP|run=%s|pos=%s|no LOW_SIDE lamp in bays %s" % (
                MARK, self.b.run_id, pos["name"], plans["C"]["info"]["bays"]))
        if not plans["E"]["info"]["floor_mids"]:
            a.log("%s_E_FLOOR_NOOP|run=%s|pos=%s|no floor slot exposes a '%s' scalar" % (
                MARK, self.b.run_id, pos["name"], p["e_rough_token"]))

    def _dcal_begin(self):
        expo = self.pos["_plans"]["D_info"]
        lo, hi = (expo["min"], expo["max"]) if expo["min"] is not None and expo["max"] is not None \
            else tuple(self.p["d_ev_clamp"])
        lo = max(float(self.p["d_ev_clamp"][0]), float(lo))
        hi = min(float(self.p["d_ev_clamp"][1]), float(hi))
        d = {"lo": lo, "hi": hi, "iters": [], "target": self.pos["base_ref"]["median"] if self.pos.get("base_ref")
             else None}
        self.pos["dcal"] = d
        if expo["manual"] or not affecting(self.pos["_plans"]["D_sources"]):
            d["skipped"] = "manual exposure" if expo["manual"] else "no post-process source affects the camera"
            self.pos["ev"] = None
            self.a.log("%s_D_NOOP|run=%s|pos=%s|%s" % (MARK, self.b.run_id, self.pos["name"], d["skipped"]))
            return
        if expo["locked"]:
            d["skipped"] = "already locked"
            self.pos["ev"] = expo["min"]
            self.a.log("%s_D_ALREADY_LOCKED|run=%s|pos=%s|ev=%s|D re-pins the same value" % (
                MARK, self.b.run_id, self.pos["name"], expo["min"]))
            return
        if d["target"] is None or int(self.p["d_cal_iters"]) < 1:
            d["skipped"] = "no base luma" if d["target"] is None else "d_cal_iters=0"
            self.pos["ev"] = (lo + hi) / 2.0
            self._fail("dcal %s %s" % (self.pos["name"], d["skipped"]))
            return
        self.queue.insert(0, ("dcal_step",))

    def _dcal_eval(self):
        d = self.pos["dcal"]
        got = self.pos.get("_dcal_last")
        luma = got["median"] if got else None
        d["iters"].append({"ev": d["trial"], "median": luma})
        if luma is not None:
            d["lo"], d["hi"] = bisect_ev(d["lo"], d["hi"], d["trial"], luma, d["target"])
        best = min((r for r in d["iters"] if r["median"] is not None),
                   key=lambda r: abs(r["median"] - d["target"]), default=None)
        close = luma is not None and abs(luma - d["target"]) <= float(self.p["d_cal_tol_abs"])
        if close or len(d["iters"]) >= int(self.p["d_cal_iters"]):
            self.pos["ev"] = best["ev"] if best else d["trial"]
            d["ev"] = self.pos["ev"]
            self.b.to_base()
            self.a.log("%s_D_CALIBRATED|run=%s|pos=%s|ev=%.3f|iters=%d|target=%.1f|best_median=%s" % (
                MARK, self.b.run_id, self.pos["name"], self.pos["ev"], len(d["iters"]), d["target"],
                "%.1f" % best["median"] if best else "none"))
            if best is None or abs(best["median"] - d["target"]) > max(float(self.p["d_cal_tol_abs"]) * 2.0, 4.0):
                self._fail("dcal %s best median %s vs base %.1f" % (self.pos["name"],
                                                                     best and best["median"], d["target"]))
            return
        self.queue.insert(0, ("dcal_step",))

    def _shoot(self, now, variant):
        sub, p, a, pos = self.sub, self.p, self.a, self.pos
        shot = pos["shots"].setdefault(variant, {"variant": variant, "stills": []})
        if not sub["begun"]:
            sub.update(begun=True, i=0, phase="issue", t_next=now)
            return
        if sub["phase"] == "issue":
            if now < sub["t_next"]:
                return
            frame = int(a.transport_frame())
            if abs(frame - pos["target_frame"]) > int(p["frame_tol_ticks"]):
                self._fail("frame %s/%s at %d target %d" % (pos["name"], variant, frame, pos["target_frame"]))
            w, h = p["resolution"]
            path = pathlib.Path(self.run["run_dir"]) / pos["name"] / ("%s_%d.png" % (variant, sub["i"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            pose = a.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
            a.console('HighResShot %dx%d filename="%s"' % (w, h, path.as_posix()))
            shot["stills"].append({"i": sub["i"], "path": path.as_posix(), "master_frame": frame, "pose": pose,
                                   "t": round(now, 3)})
            sub.update(phase="wait_file", issued=now, last_size=-1, stable=0, path=path)
            return
        if sub["phase"] == "wait_file":
            path = sub["path"]
            size = path.stat().st_size if path.is_file() else -1
            if size > int(p["file_min_bytes"]) and size == sub["last_size"]:
                sub["stable"] += 1
            else:
                sub["stable"], sub["last_size"] = 0, size
            if sub["stable"] >= int(p["file_stable_ticks"]):
                shot["stills"][-1]["bytes"] = size
                a.log("%s_STILL|run=%s|pos=%s|variant=%s|i=%d|bytes=%d|path=%s" % (
                    MARK, self.b.run_id, pos["name"], variant, sub["i"], size, path.as_posix()))
                sub["i"] += 1
                if sub["i"] >= int(p["stills_per_shot"]):
                    self.task = None
                    return
                sub.update(phase="issue", t_next=now + float(p["still_gap_s"]))
                return
            if now - sub["issued"] > float(p["file_timeout_s"]):
                raise BenchRefused("capture_timeout", path.as_posix(), self.b.run_id)


# --------------------------------------------------------------------------
# CAPTURE lifecycle (engine-free; adapter, tick registrar, store and clock injected)
# --------------------------------------------------------------------------

def arm(adapter, prepare_path=None, params=None, dry=False, out_root=OUT_ROOT, prepare_root=PREPARE_ROOT,
        owner_path=OWNER, walnut_record=WALNUT_RECORD, register=None, unregister=None, store=builtins,
        luma_reader=None, clock=time.monotonic):
    p = dict(DEFAULTS)
    p.update(params or {})
    run_id = "P02FOG-%s%s" % (utc_stamp(), "-dry" if dry else "")
    adapter.log("%s_START|run=%s|dry=%s|variants=%s" % (MARK, run_id, bool(dry), ",".join(p["variants"])))

    def refuse(exc):
        tagged = BenchRefused(exc.reason, exc.detail, run_id)
        adapter.log_error(str(tagged))
        raise tagged from exc

    try:
        bad = [v for v in p["variants"] if v not in ORDER]
        if bad or list(p["variants"])[:1] != ["base"]:
            raise BenchRefused("bad_variants", "base must come first; known %s" % ",".join(ORDER))
        if adapter.world_kind() != "game":
            raise BenchRefused("no_pie", "start PIE first (conductor_pie_begin.py); PREPARE comes before PIE")
        handles = ps.armed_handles(store)
        if handles:
            raise BenchRefused("tick_armed", ",".join(handles))
        if ps.owner_active(owner_path):
            raise BenchRefused("pie_owner_active", pathlib.Path(owner_path).as_posix())
        prep_path = find_prepare_record(prepare_root, prepare_path)
        prep = load_prepare_record(prep_path)
        if not lb.same_level(prep.get("world"), adapter.world_name()):
            raise BenchRefused("wrong_world", "prepared %s, PIE %s" % (prep.get("world"), adapter.world_name()))
        pool = adapter.pool_labels()
        missing = [l for l in pool_labels_needed(p) if l not in pool]
        if missing:
            raise BenchRefused("pool_missing", "%d %s; run PREPARE before PIE" % (len(missing), ",".join(missing)))
        lit = [l for l in pool if adapter.pool_state(l)["on"]]
        if lit:
            raise BenchRefused("pool_not_base", "%s; run RESTORE first" % ",".join(lit))
        n, seg_label = ps.passage_label(p["passage"])
        start, end = adapter.passage_segment(seg_label)
        positions = position_rows(start, end, p["positions"], p)
        census_before = adapter.census()
        floor_mats, p01_mats = adapter.floor_materials()
        walnut = walnut_state(floor_mats, p01_mats, pathlib.Path(walnut_record).is_file())
        if not walnut["applied"] and any(v in ("E", "ALL") for v in p["variants"]) \
                and p["walnut_policy"] == "require":
            raise BenchRefused("walnut_not_applied", "run p02_floor_walnut.py APPLY first (walnut_policy=require)")
    except BenchRefused as exc:
        refuse(exc)
    except Exception as exc:
        refuse(BenchRefused("arm_error", "%s: %s" % (type(exc).__name__, exc)))
    if not walnut["applied"]:
        adapter.log("%s_E_BEFORE_WALNUT|run=%s|P02 floor slots are not P01's walnut (record_exists=%s); E's floor "
                    "MIDs act on the current floor" % (MARK, run_id, walnut["record_exists"]))
    original_frame = int(adapter.transport_frame())
    run_dir = pathlib.Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    bench = FogBench(adapter, run_dir / ORIGINALS_NAME, p, run_id)
    bench.read_globals(census_before, prep)
    adapter.log("%s_ANNOUNCE|run=%s|world=PIE|P02 %s|changes PIE lights/fog/post-process/material slots only and "
                "uses %d prepared %s* fog volumes (no spawns); every change recorded and restored at the end; the "
                "map is dirty from PREPARE: Don't-Save restart after|record=%s" % (
                    MARK, run_id, ",".join(r["name"] for r in positions), len(pool_labels_needed(p)), PREFIX,
                    bench.record_path.as_posix()))
    try:
        bench.neutralise()
    except Exception:
        problems = bench.restore()
        adapter.log_error("%s_FAILED|run=%s|reason=neutralise|restored problems=%r" % (MARK, run_id, problems))
        raise
    run = {"run_id": run_id, "run_dir": run_dir.as_posix(), "dry": bool(dry), "params": plain(p),
           "positions": positions, "census_before": census_before, "original_frame": original_frame,
           "world": adapter.world_name(), "prepare_record": pathlib.Path(prep_path).as_posix(), "walnut": walnut,
           "started_utc": utc_iso(), "status": "armed", "errors": [],
           "route": "passage_stills: Master scrub (ScrubToMasterFrame) + live camera pose; no actor moved"}
    manifest = run_dir / MANIFEST_NAME
    write_verified(manifest, run)
    machine = FogMachine(bench, adapter, run, luma_reader=luma_reader)
    run["_t_start"] = clock()
    holder = {"handle": None}

    def finish(status_hint):
        run["status"] = "finishing"
        problems = []
        try:
            problems += bench.restore()
        except Exception:
            problems.append("restore raised: " + traceback.format_exc())
        if run.get("screen_messages_disabled"):
            try:
                adapter.console("EnableAllScreenMessages")
                run["screen_messages_restored"] = True
            except Exception:
                problems.append("screen messages not restored: " + traceback.format_exc())
        try:
            if adapter.world_kind() == "game":
                res = adapter.transport_scrub(original_frame)
                run["restore_scrub"] = {"frame": original_frame, "result": str(res)}
        except Exception:
            run["restore_scrub"] = {"error": traceback.format_exc()}
        census_after = adapter.census()
        run["census_after"] = census_after
        if census_after != census_before:
            problems.append("census changed %r -> %r" % (census_before, census_after))
        shots_expected = 0
        for pos in positions:
            for v, shot in (pos.get("shots") or {}).items():
                for s in shot["stills"]:
                    shots_expected += 1
                    path = pathlib.Path(s["path"])
                    s["exists"] = path.is_file()
                    if not s["exists"] or path.stat().st_size <= int(p["file_min_bytes"]):
                        problems.append("missing or undersized still: " + s["path"])
            pos.pop("_plans", None)
            pos.pop("_dcal_last", None)
        want = len(positions) * (1 if dry else len(p["variants"])) * int(p["stills_per_shot"])
        if status_hint == "complete" and shots_expected != want:
            problems.append("stills %d != expected %d" % (shots_expected, want))
        gates = list(machine.st["gate_failures"])
        run.update(gate_failures=gates, problems=problems, finished_utc=utc_iso(),
                   task_log=machine.st["task_log"], probe_timeouts=machine.st["probe_timeouts"])
        ok = status_hint == "complete" and machine.done and not problems and not gates and not run["errors"]
        run["status"] = "passed" if ok else "failed"
        bench.record["status"] = "restored" if not [x for x in problems if "!=" in x or "still" in x] else "dirty"
        try:
            bench.write()
        except Exception:
            problems.append("record write failed: " + traceback.format_exc())
        out = {k: v for k, v in run.items() if not k.startswith("_")}
        try:
            write_verified(manifest, out)
        except Exception:
            ok = False
            problems.append("manifest write/readback failed: " + traceback.format_exc())
        if unregister is not None and holder["handle"] is not None:
            unregister(holder["handle"])
        if hasattr(store, HANDLE_NAME):
            delattr(store, HANDLE_NAME)
        if ok:
            adapter.log("%s_CAPTURE_OK|run=%s|positions=%d|variants=%d|stills=%d|dir=%s" % (
                MARK, run_id, len(positions), 1 if dry else len(p["variants"]), shots_expected, run_dir.as_posix()))
        else:
            reasons = [r.split(" ")[0].split(":")[0] for r in (problems + gates)] or [status_hint]
            if run["errors"]:
                reasons.insert(0, run.get("error_reason", "error"))
            adapter.log_error("%s_FAILED|run=%s|reason=%s|problems=%r|gate_failures=%r|manifest=%s" % (
                MARK, run_id, ";".join(reasons), problems[:8], gates[:12], manifest.as_posix()))
        adapter.log("%s|run=%s|the ZZ_P02FOG_ pool and PREPARE's dirty map remain in the editor world: end PIE, then "
                    "restart the editor choosing Don't Save" % (RESTART, run_id))
        run["finished"] = True

    def tick(_delta=0.0):
        if run.get("inside") or run.get("finished"):
            return
        run["inside"] = True
        try:
            now = clock()
            if now - run["_t_start"] > float(p["run_timeout_s"]):
                raise BenchRefused("run_timeout", "%.0f s" % float(p["run_timeout_s"]), run_id)
            machine.step(now)
            if machine.done:
                finish("complete")
        except Exception as exc:
            run["errors"].append(traceback.format_exc())
            run["error_reason"] = getattr(exc, "reason", type(exc).__name__)
            try:
                finish("error")
            except Exception:
                run["errors"].append(traceback.format_exc())
                run["finished"] = True
                adapter.log_error("%s_FAILED|run=%s|reason=finish_raised" % (MARK, run_id))
        finally:
            run["inside"] = False

    if p["screen_messages"] == "off":
        adapter.console("DisableAllScreenMessages")
        run["screen_messages_disabled"] = True
    run["status"] = "capturing"
    setattr(store, STATE_NAME, run)
    if register is not None:
        holder["handle"] = register(tick)
        setattr(store, HANDLE_NAME, holder["handle"])
    adapter.log("%s_ARMED|run=%s|positions=%s|dir=%s" % (MARK, run_id, ",".join(
        "%s@%d" % (r["name"], r["target_frame"]) for r in positions), run_dir.as_posix()))
    run["_tick"] = tick
    return run


# --------------------------------------------------------------------------
# Unreal side. Everything below runs only inside the editor.
# --------------------------------------------------------------------------

def _pool_common(unreal, world, handles):
    tag = unreal.Name(TAG)

    def all_actors():
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))

    def pool_map():
        out = {}
        for actor in all_actors():
            label = actor.get_actor_label()
            if label.startswith(PREFIX) and actor.actor_has_tag(tag):
                if label in out:
                    raise RuntimeError("%s_POOL_DUPLICATE|%s" % (MARK, label))
                out[label] = actor
        handles["pool"] = out
        return out

    def pool_actor(label):
        actor = (handles.get("pool") or pool_map()).get(label) or pool_map().get(label)
        if actor is None:
            raise RuntimeError("%s_POOL_MISSING|%s" % (MARK, label))
        return actor

    def fog_comp(actor):
        return actor.get_component_by_class(unreal.LocalFogVolumeComponent)

    def census():
        lib = unreal.EditorLoadingAndSavingUtils
        return {"maps": ps.package_names(lib.get_dirty_map_packages()),
                "content": ps.package_names(lib.get_dirty_content_packages())}

    return all_actors, pool_map, pool_actor, fog_comp, census


def make_editor_adapter(unreal):
    """PREPARE: the EDITOR world, only while no PIE world exists."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = editor_sub.get_editor_world()
    handles = {}
    events = []
    all_actors, pool_map, pool_actor, fog_comp, census = _pool_common(unreal, world, handles)

    class EditorAdapter:
        def world_kind(self):
            if editor_sub.get_game_world() is not None:
                return "pie_running"
            return "editor" if world is not None else None

        def world_name(self):
            return world.get_path_name() if world else None

        def note(self, e):
            events.append(e)

        def log(self, m):
            unreal.log(m)

        def census(self):
            return census()

        def bench_actor_labels(self, prefix):
            return sorted(a.get_actor_label() for a in all_actors() if a.get_actor_label().startswith(prefix))

        def pool_labels(self):
            return sorted(pool_map())

        def pool_state(self, label):
            comp = fog_comp(pool_actor(label))
            on = bool(comp.is_visible()) or float(comp.get_editor_property("height_fog_extinction")) > 0.0 \
                or float(comp.get_editor_property("radial_fog_extinction")) > 0.0
            return {"on": on}

        def spawn_hidden(self, spec):
            """look_bench.py:1331-1366 (fog branch): editor world only, hidden, extinction 0, Movable."""
            events.append(("spawn", spec["label"]))
            actor = actor_sub.spawn_actor_from_class(unreal.LocalFogVolume, unreal.Vector(0.0, 0.0, -100000.0),
                                                     unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            if actor is None:
                raise RuntimeError("%s_SPAWN_FAILED|%s" % (MARK, spec["label"]))
            if actor.get_world() != world:
                actor_sub.destroy_actor(actor)
                raise RuntimeError("%s_SPAWN_NOT_IN_EDITOR_WORLD|%s" % (MARK, spec["label"]))
            actor.set_actor_label(spec["label"], False)
            actor.set_editor_property("tags", [unreal.Name(TAG)])
            actor.set_actor_enable_collision(False)
            comp = fog_comp(actor)
            comp.set_radial_fog_extinction(0.0)
            comp.set_height_fog_extinction(0.0)
            actor.get_editor_property("root_component").set_mobility(unreal.ComponentMobility.MOVABLE)
            comp.set_visibility(False, True)
            actor.set_actor_hidden_in_game(True)
            actor.set_is_temporarily_hidden_in_editor(True)
            handles.pop("pool", None)
            return actor.get_path_name()

    adapter = EditorAdapter()
    adapter.events = events
    return adapter


# ---- PIE ADAPTER BEGIN (no spawn / destroy / editor-actor API may appear in this region) ----
def make_pie_adapter(unreal):
    """CAPTURE / RESTORE: the PIE game world. Reads and sets properties with runtime (UFUNCTION) setters or
    set_editor_property(..., notify_mode=NEVER) on PIE objects; places, shows and hides the prepared pool."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    first = editor_sub.get_game_world()
    first_name = first.get_path_name() if first is not None else None
    handles = {}
    events = []
    _all, pool_map, pool_actor, fog_comp, census = _pool_common(unreal, first, handles)
    never = unreal.PropertyAccessChangeNotifyMode.NEVER

    def live_world():
        world = editor_sub.get_game_world()
        if world is None or first_name is None or world.get_path_name() != first_name:
            return None
        return world

    def actors_of(cls):
        world = live_world()
        if world is None or cls is None:
            return []
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, cls))

    def show_root():
        roots = actors_of(unreal.InfinityStageShowRoot)
        if len(roots) != 1 or not roots[0].sequence_player:
            raise BenchRefused("no_show_root", "runtime Show Roots: %d" % len(roots))
        return roots[0]

    def get(oid):
        obj = handles.get(oid)
        if obj is None:
            obj = unreal.find_object(None, oid)
            if obj is None:
                raise RuntimeError("%s_UNRESOLVED|%s" % (MARK, oid))
            handles[oid] = obj
        return obj

    def light_comp(actor):
        comps = list(actor.get_components_by_class(unreal.LocalLightComponent))
        return comps[0] if len(comps) == 1 else None

    def rot_dict(r):
        return {"roll": float(r.roll), "pitch": float(r.pitch), "yaw": float(r.yaw)}

    def vec(v):
        return [float(v.x), float(v.y), float(v.z)]

    def pp_struct(obj):
        if isinstance(obj, unreal.PostProcessVolume):
            return obj.get_editor_property("settings")
        return obj.get_editor_property("post_process_settings")

    def pp_set(obj, s):
        if isinstance(obj, unreal.PostProcessVolume):
            obj.set_editor_property("settings", s, notify_mode=never)
        else:
            obj.set_editor_property("post_process_settings", s, notify_mode=never)

    def fog_read(comp, field):
        if field == "fog_density":
            return float(comp.get_editor_property("fog_density"))
        if field == "second_fog_density":
            return float(comp.get_editor_property("second_fog_data").get_editor_property("fog_density"))
        if field == "volumetric_fog":
            for name in ("enable_volumetric_fog", "volumetric_fog"):
                try:
                    return bool(comp.get_editor_property(name))
                except Exception:
                    continue
            raise RuntimeError("%s_FOG_FIELD|volumetric_fog" % MARK)
        raise RuntimeError("%s_FOG_FIELD|%s" % (MARK, field))

    def make_mid(spec):
        """look_bench.py:1390-1403."""
        parent = unreal.load_object(None, spec["mid_parent"])
        lib = getattr(unreal, "MaterialLibrary", None) or getattr(unreal, "KismetMaterialLibrary", None)
        if lib is not None and hasattr(lib, "create_dynamic_material_instance"):
            mid = lib.create_dynamic_material_instance(live_world(), parent)
        else:
            mid = unreal.MaterialInstanceDynamic.create(parent, None)
        for name, value in spec.get("scalars", {}).items():
            mid.set_scalar_parameter_value(name, float(value))
        return mid

    def bounds(actor):
        o, e = actor.get_actor_bounds(False)
        return o, e

    class PieAdapter:
        def world_kind(self):
            return "game" if live_world() is not None else None

        def world_name(self):
            return first_name

        def note(self, e):
            events.append(e)

        def log(self, m):
            unreal.log(m)

        def log_error(self, m):
            unreal.log_error(m)

        def census(self):
            return census()

        # ---- transport + camera (passage_stills.py:637-668)
        def passage_segment(self, label):
            segs = [s for s in list(show_root().transport.segments)
                    if s.type == unreal.InfinityCueType.WING_PAIR and str(s.label) == label]
            if len(segs) != 1:
                raise BenchRefused("no_segment", "%s segments: %d" % (label, len(segs)))
            return int(segs[0].start_frame.value), int(segs[0].end_frame.value)

        def transport_scrub(self, frame):
            root = show_root()
            root.sequence_player.pause()
            return root.transport.scrub_to_master_frame(unreal.FrameNumber(int(frame)))

        def transport_pause(self):
            show_root().sequence_player.pause()

        def transport_frame(self):
            return int(show_root().transport.get_current_master_frame().value)

        def camera_pose(self, aspect, fov_fallback):
            world = live_world()
            cam = unreal.GameplayStatics.get_player_camera_manager(world, 0) if world is not None else None
            if cam is None:
                return None
            loc, rot = cam.get_camera_location(), cam.get_camera_rotation()
            fov = float(cam.get_fov_angle() or 0.0)
            return {"loc": vec(loc), "rot": rot_dict(rot), "fov_deg": fov if fov > 1.0 else float(fov_fallback),
                    "fov_read": fov, "aspect": float(aspect)}

        def console(self, command):
            world = live_world()
            if world is None:
                raise BenchRefused("pie_ended", "console with no PIE world")
            unreal.SystemLibrary.execute_console_command(world, command)

        # ---- reads for the plans
        def lights(self):
            rows = []
            skip = tuple(getattr(unreal, n) for n in SKIP_LIGHT_CLASSES if hasattr(unreal, n))
            for actor in actors_of(unreal.Actor):
                label = actor.get_actor_label()
                if label.startswith(PREFIX) or (skip and isinstance(actor, skip)):
                    continue
                comp = light_comp(actor)
                if comp is None:
                    continue
                lid = actor.get_path_name()
                handles[lid] = actor
                rows.append({"id": lid, "label": label, "location": vec(actor.get_actor_location()),
                             "rotation": rot_dict(actor.get_actor_rotation()),
                             "volumetric_scattering_intensity": float(
                                 comp.get_editor_property("volumetric_scattering_intensity")),
                             "visible": bool(comp.is_visible()), "intensity": float(comp.get_editor_property("intensity"))})
            return sorted(rows, key=lambda r: r["id"])

        def fogs(self):
            rows = []
            for actor in actors_of(unreal.ExponentialHeightFog):
                comp = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
                cid = comp.get_path_name()
                handles[cid] = comp
                rows.append({"id": cid, "label": actor.get_actor_label(), "fog_density": fog_read(comp, "fog_density"),
                             "second_fog_density": fog_read(comp, "second_fog_density"),
                             "volumetric_fog": fog_read(comp, "volumetric_fog")})
            return rows

        def media(self):
            rows = []
            for actor in actors_of(getattr(unreal, "InfinityStageEffectSource", None)):
                comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
                if comp is None:
                    continue
                cid = comp.get_path_name()
                handles[cid] = comp
                rows.append({"id": cid, "label": actor.get_actor_label(), "location": vec(comp.get_world_location()),
                             "radial_fog_extinction": float(comp.get_editor_property("radial_fog_extinction")),
                             "height_fog_extinction": float(comp.get_editor_property("height_fog_extinction"))})
            return rows

        def pp_sources(self, cam_loc):
            rows = []
            point = unreal.Vector(*cam_loc)
            fields = PP_EXPOSURE + PP_READ_ONLY + tuple(E_PP_OVERRIDE.values()) + tuple(E_PP_OVERRIDE)
            for v in actors_of(unreal.PostProcessVolume):
                enabled = bool(v.get_editor_property("enabled"))
                unbound = bool(v.get_editor_property("unbound"))
                contains = unbound
                if not unbound:
                    try:                     # AVolume::EncompassesPoint has NO UFUNCTION (Volume.h:52), so this
                        got = v.encompasses_point(point, 0.0)      # normally raises; kept in case a binding exists
                        contains = bool(got[0] if isinstance(got, tuple) else got)
                    except Exception:        # the actor bounds box [inf: a box, not the brush shape]
                        o, e = bounds(v)
                        contains = all(abs(c - oc) <= ec for c, oc, ec in zip(cam_loc, (o.x, o.y, o.z),
                                                                              (e.x, e.y, e.z)))
                vid = v.get_path_name()
                handles[vid] = v
                s = pp_struct(v)
                rows.append({"id": vid, "kind": "ppv", "label": v.get_actor_label(), "enabled": enabled,
                             "unbound": unbound, "priority": float(v.get_editor_property("priority")),
                             "weight": float(v.get_editor_property("blend_weight")),
                             "affects": enabled and contains and float(v.get_editor_property("blend_weight")) > 0.0,
                             "fields": {f: plain_pp(s.get_editor_property(f)) for f in fields}})
            world = live_world()
            mgr = unreal.GameplayStatics.get_player_camera_manager(world, 0) if world is not None else None
            target = mgr.get_view_target() if mgr is not None else None
            comp = target.get_component_by_class(unreal.CameraComponent) if target is not None else None
            if comp is not None:
                cid = comp.get_path_name()
                handles[cid] = comp
                s = pp_struct(comp)
                weight = float(comp.get_editor_property("post_process_blend_weight"))
                rows.append({"id": cid, "kind": "camera", "label": target.get_actor_label(), "enabled": True,
                             "unbound": True, "priority": 1e9, "weight": weight, "affects": weight > 0.0,
                             "fields": {f: plain_pp(s.get_editor_property(f)) for f in fields}})
            return rows

        def floor_slots(self):
            rows = []
            for actor in actors_of(unreal.StaticMeshActor):
                if actor.get_actor_label() not in FLOOR_SLABS:
                    continue
                comp = actor.static_mesh_component
                cid = comp.get_path_name()
                handles[cid] = comp
                for i in range(comp.get_num_materials()):
                    mat = comp.get_material(i)
                    rows.append({"id": cid, "slot": i, "material": mat.get_path_name() if mat else None,
                                 "label": actor.get_actor_label()})
            return rows

        def floor_materials(self):
            p02, p01 = [], []
            for actor in actors_of(unreal.StaticMeshActor):
                label = actor.get_actor_label()
                if label in FLOOR_SLABS or label == P01_SLAB:
                    mats = [m.get_path_name() if m else None for m in actor.static_mesh_component.get_materials()]
                    (p01 if label == P01_SLAB else p02).extend(mats)
            return p02, p01

        def floor_top_z(self, cam_loc):
            best = None
            for actor in actors_of(unreal.StaticMeshActor):
                if actor.get_actor_label() not in FLOOR_SLABS:
                    continue
                o, e = bounds(actor)
                if abs(cam_loc[0] - o.x) <= e.x and abs(cam_loc[1] - o.y) <= e.y:
                    top = float(o.z + e.z)
                    best = top if best is None else max(best, top)
            return best

        def wing_slots(self, pose, radius, slot_name):
            rows = []
            fwd = lb.rotator_axes(pose["rot"]["yaw"], 0.0, 0.0)[0]
            for actor in actors_of(unreal.Actor):
                label = actor.get_actor_label()
                if label.startswith(PREFIX) or label in FLOOR_SLABS:
                    continue
                for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                    idx = comp.get_material_index(slot_name)
                    if idx < 0:
                        continue
                    origin, extent, _r = unreal.SystemLibrary.get_component_bounds(comp)
                    d = [origin.x - pose["loc"][0], origin.y - pose["loc"][1], origin.z - pose["loc"][2]]
                    reach = math.sqrt(sum(x * x for x in d)) - math.sqrt(extent.x ** 2 + extent.y ** 2 + extent.z ** 2)
                    if reach > radius or (d[0] * fwd[0] + d[1] * fwd[1]) < -math.hypot(extent.x, extent.y):
                        continue
                    cid = comp.get_path_name()
                    handles[cid] = comp
                    mat = comp.get_material(idx)
                    rows.append({"id": cid, "slot": int(idx), "material": mat.get_path_name() if mat else None})
            return sorted(rows, key=lambda r: (r["id"], r["slot"]))

        def scalar_params(self, material_path):
            out = {}
            try:
                mat = unreal.load_object(None, material_path)
                names = unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat)
                for n in names:
                    name = str(n)
                    if isinstance(mat, unreal.MaterialInstance):
                        out[name] = float(mat.get_scalar_parameter_value(name))
                    else:
                        out[name] = float(unreal.MaterialEditingLibrary.get_material_default_scalar_parameter_value(
                            mat, name))
            except Exception as exc:                 # report, never guess
                unreal.log_warning("%s_SCALARS_UNREAD|%s|%r" % (MARK, material_path, exc))
            return out

        # ---- generic property access by (kind, id, field)
        def read(self, kind, oid, field):
            if kind == "light":
                actor = get(oid)
                if field == "rotation":
                    return rot_dict(actor.get_actor_rotation())
                return float(light_comp(actor).get_editor_property(field))
            if kind == "fog":
                return fog_read(get(oid), field)
            if kind == "media":
                return float(get(oid).get_editor_property(field))
            if kind == "pp":
                return plain_pp(pp_struct(get(oid)).get_editor_property(field))
            if kind == "mid":
                mat = get(oid).get_material(int(field[4:]))
                return mat.get_path_name() if mat else None
            if kind == "cvar":
                return float(unreal.SystemLibrary.get_console_variable_float_value(oid))
            raise RuntimeError("%s_BAD_KIND|%s" % (MARK, kind))

        def write(self, kind, oid, field, value):
            events.append(("write", kind, oid, field))
            if kind == "light":
                actor = get(oid)
                if field == "rotation":
                    actor.set_actor_rotation(unreal.Rotator(roll=float(value["roll"]), pitch=float(value["pitch"]),
                                                            yaw=float(value["yaw"])), False)
                elif field == "volumetric_scattering_intensity":
                    light_comp(actor).set_volumetric_scattering_intensity(float(value))
                else:
                    raise RuntimeError("%s_LIGHT_FIELD|%s" % (MARK, field))
            elif kind == "fog":
                comp = get(oid)
                if field == "fog_density":
                    comp.set_fog_density(float(value))
                elif field == "second_fog_density":
                    comp.set_second_fog_density(float(value))
                elif field == "volumetric_fog":
                    comp.set_volumetric_fog(bool(value))
                else:
                    raise RuntimeError("%s_FOG_FIELD|%s" % (MARK, field))
            elif kind == "media":
                comp = get(oid)
                if field == "radial_fog_extinction":
                    comp.set_radial_fog_extinction(float(value))
                elif field == "height_fog_extinction":
                    comp.set_height_fog_extinction(float(value))
                else:
                    raise RuntimeError("%s_MEDIA_FIELD|%s" % (MARK, field))
            elif kind == "pp":
                obj = get(oid)
                s = pp_struct(obj)
                cur = s.get_editor_property(field)
                s.set_editor_property(field, type(cur)(value) if isinstance(cur, (bool, float, int)) else value)
                pp_set(obj, s)
            elif kind == "mid":
                comp = get(oid)
                slot = int(field[4:])
                if value is None or isinstance(value, str):
                    comp.set_material(slot, unreal.load_object(None, value) if value else None)
                else:
                    comp.set_material(slot, make_mid(value))
            elif kind == "cvar":
                unreal.SystemLibrary.execute_console_command(live_world(), "%s %s" % (oid, value))
            else:
                raise RuntimeError("%s_BAD_KIND|%s" % (MARK, kind))

        # ---- show strobes and sweep lights (look_bench.py:1495-1515; bSweepEnabled hides the light,
        #      InfinityStageSweepLight.cpp:243-258)
        def _flag_rows(self, cls_name, prop):
            rows = []
            for actor in actors_of(getattr(unreal, cls_name, None)):
                sid = actor.get_path_name()
                handles[sid] = actor
                rows.append({"id": sid, "label": actor.get_actor_label(), "enabled": bool(actor.get_editor_property(prop))})
            return sorted(rows, key=lambda r: r["id"])

        def show_strobes(self):
            return self._flag_rows("InfinityStageStrobeLight", "strobe_enabled")

        def show_strobe_enabled(self, sid):
            return bool(get(sid).get_editor_property("strobe_enabled"))

        def set_show_strobe(self, sid, enabled):
            events.append(("set_strobe", sid))
            get(sid).set_editor_property("strobe_enabled", bool(enabled), notify_mode=never)

        def sweep_lights(self):
            return self._flag_rows("InfinityStageSweepLight", "sweep_enabled")

        def sweep_enabled(self, sid):
            return bool(get(sid).get_editor_property("sweep_enabled"))

        def set_sweep(self, sid, enabled):
            events.append(("set_sweep", sid))
            get(sid).set_editor_property("sweep_enabled", bool(enabled), notify_mode=never)

        # ---- the prepared pool (place, show, hide; never create)
        def pool_labels(self):
            return sorted(pool_map())

        def pool_state(self, label):
            comp = fog_comp(pool_actor(label))
            on = bool(comp.is_visible()) or float(comp.get_editor_property("height_fog_extinction")) > 0.0 \
                or float(comp.get_editor_property("radial_fog_extinction")) > 0.0
            return {"on": on}

        def show_pool(self, spec):
            events.append(("show", spec["label"]))
            actor = pool_actor(spec["label"])
            comp = fog_comp(actor)
            actor.set_actor_location_and_rotation(unreal.Vector(*spec["loc"]),
                                                  unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(spec["yaw"])),
                                                  False, True)
            got = actor.get_actor_location()
            if math.dist((got.x, got.y, got.z), tuple(spec["loc"])) > 1.0:
                raise RuntimeError("%s_MOVE_FAILED|%s (not Movable?)" % (MARK, spec["label"]))
            s = float(spec["scale"])
            actor.set_actor_scale3d(unreal.Vector(s, s, s))
            comp.set_radial_fog_extinction(float(spec["radial"]))
            comp.set_height_fog_extinction(float(spec["height"]))
            comp.set_height_fog_falloff(float(spec["falloff"]))
            comp.set_height_fog_offset(float(spec["offset"]))
            comp.set_fog_phase_g(float(spec["phase_g"]))
            comp.set_visibility(True, True)
            actor.set_actor_hidden_in_game(False)

        def hide_pool(self, label):
            events.append(("hide", label))
            actor = pool_actor(label)
            comp = fog_comp(actor)
            comp.set_radial_fog_extinction(0.0)
            comp.set_height_fog_extinction(0.0)
            comp.set_visibility(False, True)
            actor.set_actor_hidden_in_game(True)

    adapter = PieAdapter()
    adapter.events = events
    return adapter


def plain_pp(v):
    """PostProcessSettings values -> JSON-able (enums as their string, numbers as float / bool)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return str(v)
# ---- PIE ADAPTER END ----


def main():
    import unreal
    g = globals()
    mode = g.get("BENCH_MODE", "")
    params = dict(g.get("BENCH_PARAMS", {}) or {})
    if mode == "PREPARE":
        adapter = make_editor_adapter(unreal)
        run_id = "P02FOGPREP-" + utc_stamp()
        run_dir = PREPARE_ROOT / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        try:
            PrepareBench(adapter, run_dir / PREPARE_RECORD_NAME, params, run_id).run()
        except BenchRefused as exc:
            unreal.log_error(str(exc))
            raise
        return
    if mode == "RESTORE":
        adapter = make_pie_adapter(unreal)
        run_id = "P02FOGRESTORE-" + utc_stamp()
        if adapter.world_kind() != "game":
            unreal.log_error("%s_FAILED|run=%s|reason=no_pie|RESTORE works on the PIE copies" % (MARK, run_id))
            raise RuntimeError("no PIE")
        armed = ps.armed_handles(builtins)
        if HANDLE_NAME in armed:
            unreal.log_error("%s_FAILED|run=%s|reason=tick_armed|a capture is still running; it restores itself"
                             % (MARK, run_id))
            raise RuntimeError("armed")
        explicit = g.get("BENCH_RECORD")
        records = ([explicit] if isinstance(explicit, (str, pathlib.Path)) else list(explicit)) if explicit else \
            sorted(OUT_ROOT.glob("P02FOG-*/" + ORIGINALS_NAME))
        problems = restore_all(adapter, records, unreal.log)
        if problems:
            unreal.log_error("%s_FAILED|run=%s|reason=restore|problems=%r" % (MARK, run_id, problems[:8]))
        else:
            unreal.log("%s_RESTORE_OK|run=%s|records=%d" % (MARK, run_id, len(records)))
        unreal.log("%s|run=%s|end PIE, then restart the editor choosing Don't Save" % (RESTART, run_id))
        return
    if mode == "CAPTURE":
        adapter = make_pie_adapter(unreal)
        return arm(adapter, g.get("BENCH_PREPARE_RECORD"), params, bool(g.get("BENCH_DRY", False)),
                   register=unreal.register_slate_post_tick_callback,
                   unregister=unreal.unregister_slate_post_tick_callback)["run_dir"]
    raise RuntimeError("%s_BAD_MODE|%r" % (MARK, mode))


if __name__ == "__main__" or "BENCH_MODE" in globals():
    main()
