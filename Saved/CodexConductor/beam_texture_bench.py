"""BEAM TEXTURE BENCH: a reversible, NON-SAVING A/B of "body" in ONE big light beam, captured as stills Gary picks
from (Gary, 6 Oct ~17:45, GARY_PIE_NOTES_2026-10-06_overnight.md:159-161: the beams "lack texture"; approved a bench
"especially for the big beams").

THE BAY (default P01 bay 20, its BEAM_R). Why this one:
  - Gary named it: "keep the one that flickers nicely" (GARY_PIE_NOTES_2026-10-05.md:259) = "bay 20's orange BEAM_R"
    (GARY_PIE_NOTES_2026-10-06_overnight.md:48) [declaration-proven: the notes].
  - It survives the pending P01 rescore unchanged: lighting_scores.json P01 segment 13-40, bay 20 note "the original
    orange BEAM_R, unchanged (steady, strike 650 cm)" [declaration-proven], so what we learn transfers. P01's round-2
    rescore is HELD (GARY_PIE_NOTES_2026-10-06_overnight.md:61-68), so the LIVE P01 is the 5 Oct score
    (lighting_scores_record_P01.json, status saved_readback_verified) [declaration-proven: the record].
  - It is a top-tier beam: 3500 cd, volumetric_scattering 6.0, outer cone 7 deg, attenuation 2600 cm, cast_shadows
    False, cast_volumetric_shadow False, no light function, ignition_stutter 0 (record after_rows for "P01 SCORE B20
    P01_WARM_THEATRICAL BEAM_R") [declaration-proven: the record]. Steady = no flicker noise inside the texture metric.
  - It strikes on approach at 650 cm with a 150 cm ramp (InfinityStageLightDrama.cpp:24-32, :89-91: strike when
    lamp route distance - camera route distance <= StrikeDistanceCm) [declaration-proven], so it is lit only when it
    is close, i.e. big in frame. Station-local pose (-150, -1250, 140) cm, yaw 76 deg, pitch -5 deg [measured: quat in
    the record -> forward (0.241, 0.967, -0.087)]: a low raking shaft from the -Y wall across the route, crossing the
    centre line ~312 cm past the lamp at knee height. The camera positions are LOCATED live (see below), not guessed.
  - The alternative (P01 bay 3, "the shaft crossing the red curtain" at the P01 start) is in the strike cascade with
    ignition_stutter 0.45 and next to the Opening's curtain/strobe beats [inferred: less repeatable stills]. Set
    params {"bay": 3} to bench it instead; nothing else is bay-specific.

VARIANTS (each applied from the recorded base; base first; a base return between variants):
  base  nothing changed.
  A     volumetric shadows + occluders. The beam's SpotLightComponent gets cast_shadows True AND cast_volumetric_shadow
        True (UFUNCTIONs LightComponentBase.h:146 SetCastShadows, :153 SetCastVolumetricShadow; look_bench.py:1414-1417
        used the same setters live) - PIE copy only. A volumetric shadow needs an occluder, so the plan MEASURES what
        sits between the lamp and the route: a fan of line traces (KismetSystemLibrary.h:1270 LineTraceSingle) from the
        lamp along the cone to where the axis crosses the camera route, plus a positive control (a trace down from
        the camera must hit the floor, or the traces are "blind"). Verdict per run: clear (< 5 % of rays blocked),
        partial (5-90 %: a pierced wing / the rig already cuts the beam: no ZZ_ occluder needed), blocked (> 90 %:
        with shadows ON the beam would die -> the light needs moving; reported as behind_wing advice), blind
        (control failed). With a_occluder_policy "auto" the prepared ZZ_ occluder is shown only when clear or blind:
        a_occluder "bars" (default) = a_bar_count thin black rods, horizontal and perpendicular to the beam, stacked
        across the cone a_occ_distance_cm in front of the lamp (horizontal slits make horizontal light sheets, which a
        camera looking along the route sees edge-on as stripes; vertical slits would be seen face-on and merge), or
        "breakup" = a plane with a MASKED black material whose opacity is an existing engine texture
        (/Engine/MaterialTemplates/Textures/T_Noise01: Texture2D, TC_Default [binary-proven: strings in the
        .uasset]) thresholded - a cucoloris.
  B     uneven fog density. A Local Fog Volume cannot follow noise (its density is analytic radial + height,
        VolumetricFog.usf:233-235) [declaration-proven], so B uses a prepared ZZ_ CUBE with a CREATE-ONLY
        Volume-domain material (/Game/ZZ_Bench/BeamTexture/M_ZZ_BeamTex_NoiseVolume) whose Extinction is a
        3-octave 3D value noise of absolute world position. Volume-domain primitives are voxelised into volumetric fog
        with Albedo = BaseColor, Extinction = SubsurfaceColor.r (non-Substrate) or the VolumetricFogCloud BSDF
        (Substrate), Emissive, in 1/m (x 1/100 -> 1/cm) and masked to the object's local bounds in box mode
        (VolumetricFogVoxelization.usf:29-41, :265-290, :324-343) [declaration-proven, shader source]. Is a
        pseudo-volume texture or noise node available? A real VolumeTexture exists (/Engine/EngineSky/VolumetricClouds/
        T_VolumeNoiseShape64: "VolumeTexture", TC_Masks [binary-proven]) but sampling one has never been built in this
        project; the noise is therefore computed in a Custom node (MaterialExpressionCustom: 17 uses in the project's
        builders; the hash/value-noise construction is s3_marble_tiling_material.py:330-369, compiled and applied
        6 Oct), fed by WorldPosition -> TruncateLWC (same file :537-540) and Time. Only proven node classes are used.
        The cube is aligned to the beam, wrapping it from a_occ_distance_cm to past the route. Global height fog
        density x b_fog_density_scale (0.75) so the noise reads. Whether a STATIC MESH (not a particle) with a Volume
        material is voxelised, and how Substrate converts the legacy pins, are [inferred]: the live run must confirm
        (B's texture metric vs base; PREPARE logs r.Substrate).
  BL    (optional, not in the default list) fallback for B if the volume mesh does nothing: bl_count prepared ZZ_ Local
        Fog Volumes of varied radius and density strung along the beam (LFVs are live-proven: look_bench, fog bench).
  D     fog rendering, PIE only, every original recorded and restored: r.VolumetricFog.GridPixelSize 8 -> 4,
        r.VolumetricFog.GridSizeZ 64 -> 128, r.VolumetricFog.HistoryWeight lowered (less temporal reprojection), and the
        height fog's VolumetricFogScatteringDistribution 0.2 -> 0.7 (ExponentialHeightFogComponent.h:144, setter :308).
        CVar names binary-proven (UTF-16 strings in UnrealEditor-Renderer.dll). NOTE [measured: Saved/Logs/
        PussStage.log:736-737, :921, editor start 6 Oct 20:35] scalability Cine already set GridPixelSize 4 and
        GridSizeZ 128, so the brief's targets are already the base; with d_escalate True (default) D goes one step
        further (GridPixelSize 2, GridSizeZ 256) and the manifest says so (d_plan.escalated). NOTE the header comment
        (ExponentialHeightFogComponent.h:139-142): "to have visible volumetric fog light shafts from the side, the
        distribution will need to be closer to 0"; this beam is seen from the side, so 0.7 is expected to DIM it.
  C     dust motes: SKIPPED. Niagara is not authorable from Python here (P04RainBench/p04_rain_bench_probe.json:
        authorable false, class_not_exposed NiagaraStatelessEmitter [measured 6 Oct]); the C++ Motes effect type
        (InfinityStageEffectTypes.h:59-60) spawns /Game/Scenes/Effects/BP_Effect_Motes
        (InfinityStageEffectSource.cpp:61-62), which does NOT exist in Content [measured: Content/Scenes/Effects holds
        only the candle]. Noted for the Niagara session.
  ALL   A + B + D.

CAMERA POSITIONS (positions param, default ahead 450 / 250 / 50 cm): the camera is placed by Master scrub
(passage_stills route) at the frame where the lamp is ahead_cm in front of it along the camera's heading. A secant
search ("locate", <= locate_max_iter scrubs) finds the frame live; no frame is guessed. Each shot records whether
the beam is struck (live intensity) and whether its core mask is in frame.

METRICS (offline, beam_texture_bench_contact_sheet.py): for each position the beam's core is projected into the
frame (camera pose + beam axis + cone, from the manifest) as a mask; inside it, on the mean of the shot's stills
(temporal noise averages out, spatial texture stays), "texture" = std of the high-passed luma (luma - box blur),
relative to the mean luma. A variant is "textured" when that is >= textured_ratio x base AND the beam keeps >=
keep_brightness of base's mean. The base vs itself is the failing control (ratio 1). Frame time = editor tick deltas
over time_seconds with no capture in flight (lb.frame_stats; comparable within one run only).

Modes (BENCH_MODE): PREPARE (editor world, PIE NOT running: creates the three bench materials CREATE-ONLY under
/Game/ZZ_Bench/BeamTexture and spawns the hidden ZZ_BEAMTEX_* pool; never saves), CAPTURE (PIE: the stills run;
BENCH_DRY=True only locates, settles, plans and shoots base), RESTORE (PIE: re-applies every original from this
session's records, hides the pool). The map and three new material packages are dirty after PREPARE by design; the
conductor ends with a Don't-Save editor restart (it also discards the new materials).

Markers carry run ids: BEAM_TEXTURE_BENCH_START|run=..., _ANNOUNCE, _LOCATE, _PLAN, _OCCLUSION, _TIME, _STILL,
_PREPARE_OK, _CAPTURE_OK (only after restore verified, census equal, every still on disk, manifest read back),
_RESTORE_OK, _FAILED|run=...|reason=..., _NEEDS_DONT_SAVE_RESTART.

Rules (memory + look_bench / p02_fog_bench): originals READ and WRITTEN (fsync, re-read) before the first change of
each position; no save call anywhere (harness scan); no spawn / destroy in the PIE adapter or the engine-free classes
(harness scan); Unreal objects only inside closures; no exposure override (show exposure; the unbound PPV's lock is
recorded read-only); create-only materials, never a node deleted.
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
import p02_fog_bench as fb
import passage_stills as ps

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
OUT_ROOT = BASE / "BeamTextureBench"
PREPARE_ROOT = OUT_ROOT / "_prepare"
LOG_PATH = BASE.parent / "Logs" / "PussStage.log"
PREPARE_RECORD_NAME = "beam_texture_bench_prepare.json"
ORIGINALS_NAME = "beam_texture_bench_originals.json"
MANIFEST_NAME = "beam_texture_bench_manifest.json"
OWNER = BASE / "pie_recording_owner.json"
PREFIX = "ZZ_BEAMTEX_"
TAG = "ZZ_BEAMTEX"
HANDLE_NAME = "PUSS_BEAM_TEXTURE_BENCH_HANDLE"
STATE_NAME = "PUSS_BEAM_TEXTURE_BENCH_STATE"
MARK = "BEAM_TEXTURE_BENCH"
RESTART = MARK + "_NEEDS_DONT_SAVE_RESTART"
ORDER = ("base", "A", "B", "BL", "D", "ALL")
DEFAULT_VARIANTS = ("base", "A", "B", "D", "ALL")
KINDS = ("light", "fog", "cvar")
ASSET_DIR = "/Game/ZZ_Bench/BeamTexture"
MAT_NOISE = ASSET_DIR + "/M_ZZ_BeamTex_NoiseVolume"
MAT_BREAKUP = ASSET_DIR + "/M_ZZ_BeamTex_Breakup"
MAT_BLACK = ASSET_DIR + "/M_ZZ_BeamTex_Black"
BENCH_MATERIALS = (MAT_BLACK, MAT_BREAKUP, MAT_NOISE)
CUBE = "/Engine/BasicShapes/Cube.Cube"            # 100 cm cube, pivot at centre (look_bench.py:107)
PLANE = "/Engine/BasicShapes/Plane.Plane"         # 100 x 100 cm, normal +Z [inferred: engine basic shape]
SKIP_LIGHT_CLASSES = ("InfinityStageSweepLight", "InfinityStageStrobeLight")

DEFAULTS = {
    "passage": "P01",
    "bay": 20,
    "bay_count": 48,                   # lighting_scores_record_P01.json plan.bay_count
    "beam_token": "BEAM_R",            # label "P01 SCORE B20 P01_WARM_THEATRICAL BEAM_R"
    # where the camera stands: the lamp is ahead_cm in front of it (strike at 650, full at 500 for bay 20)
    "positions": ({"name": "a450", "ahead_cm": 450.0}, {"name": "a250", "ahead_cm": 250.0},
                  {"name": "a050", "ahead_cm": 50.0}),
    "locate_tol_cm": 60.0,
    "locate_max_iter": 8,
    "locate_wait_s": 0.4,
    "locate_first_step_bays": 0.35,
    "locate_max_step_bays": 3.0,
    "variants": DEFAULT_VARIANTS,
    "resolution": (1600, 900),
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
    "settle_trend": True,
    "base_return_tol_abs": 4.0,
    "base_return_tol_rel": 0.10,
    "base_return_iqr_k": 1.0,
    "frame_tol_ticks": 1,
    "file_min_bytes": 1000,
    "file_stable_ticks": 4,
    "file_timeout_s": 45.0,
    "fov_fallback_deg": 90.0,
    "run_timeout_s": 1500.0,
    "rot_tol_deg": 1e-3,
    "time_seconds": 3.0,
    "show_strobes": "off",
    "sweep_lights": "off",
    "screen_messages": "off",
    "struck_min_intensity": 1.0,
    # mask
    "mask_samples": 32,
    "mask_core": 0.6,
    "mask_past_route_cm": 300.0,
    "mask_start_extra_cm": 60.0,
    "mask_min_frac": 0.004,
    "mask_grid": (160, 90),
    # texture metric (offline, contact sheet)
    "analysis_width": 480,
    "hp_blur_frac": 0.012,             # box-blur radius as a fraction of the analysis width (~6 px at 480)
    "textured_ratio": 1.25,
    "keep_brightness": 0.25,
    # A
    "a_occluder_policy": "auto",      # "auto" | "always" | "never"
    "a_occluder": "bars",             # "bars" | "breakup"
    "a_occ_distance_cm": 200.0,
    "a_bar_count": 4,
    "a_bar_thick_cm": 4.0,
    "a_bar_len_k": 1.8,
    "a_breakup_size_k": 1.6,
    "a_breakup_texture": "/Engine/MaterialTemplates/Textures/T_Noise01.T_Noise01",
    "a_breakup_tiling": 3.0,
    "a_breakup_threshold": 0.5,
    "a_breakup_contrast": 6.0,
    "a_trace_start_cm": 30.0,
    "a_trace_rings": ((0.5, 6), (0.95, 6)),
    "a_clear_max_frac": 0.05,
    "a_blocked_min_frac": 0.9,
    "a_control_drop_cm": 600.0,
    "a_wing_radius_cm": 900.0,
    "a_wing_max_rows": 40,
    "a_wing_max_extent_cm": 3000.0,
    "a_behind_cm": 150.0,
    # B
    "b_fog_density_scale": 0.75,
    "b_noise_cm": 120.0,
    "b_noise_contrast": 1.8,
    "b_noise_floor": 0.15,
    "b_extinction_peak": 0.35,         # 1/m, same unit as LFV extinction (VolumetricFog.usf:268-269); P01 haze media
    "b_albedo": 0.9,                   #   use 0.15 (record), look_bench haze 0.04-0.22 [inferred look value]
    "b_drift_cm_s": 0.0,               # 0 keeps stills repeatable; the show could drift it
    "b_box_margin_cm": 80.0,
    # BL
    "bl_count": 6,
    "bl_radius_min_cm": 90.0,
    "bl_radius_max_cm": 220.0,
    "bl_ext_min": 0.05,
    "bl_ext_max": 0.35,
    "bl_seed": 20,
    "bl_phase_g": 0.2,
    # D
    "d_cvars": {"r.VolumetricFog.GridPixelSize": 4.0, "r.VolumetricFog.GridSizeZ": 128.0,
                "r.VolumetricFog.HistoryWeight": 0.6},
    "d_escalate": True,
    "d_scattering_distribution": 0.7,
}


class BenchRefused(RuntimeError):
    def __init__(self, reason, detail="", run="?"):
        self.reason, self.detail = reason, str(detail)
        super().__init__("%s_FAILED|run=%s|reason=%s%s" % (MARK, run, reason, ("|" + self.detail) if detail else ""))


# --------------------------------------------------------------------------
# pure helpers (no Unreal): tested offline by test_beam_texture_bench.py
# --------------------------------------------------------------------------

utc_stamp, utc_iso, plain, same_value, stats = fb.utc_stamp, fb.utc_iso, fb.plain, fb.same_value, fb.stats
robust_settle, base_return_ok = fb.robust_settle, fb.base_return_ok


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


def beam_regex(p):
    n, _seg = ps.passage_label(p["passage"])
    return r"^P%02d SCORE B%02d .*%s$" % (n, int(p["bay"]), re.escape(str(p["beam_token"])))


def vadd(a, b):
    return tuple(float(x) + float(y) for x, y in zip(a, b))


def vsub(a, b):
    return tuple(float(x) - float(y) for x, y in zip(a, b))


def vmul(a, k):
    return tuple(float(x) * float(k) for x in a)


def vdot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def vunit(a):
    n = math.sqrt(vdot(a, a))
    if n < 1e-9:
        raise ValueError("%s_ZERO_VECTOR" % MARK)
    return vmul(a, 1.0 / n)


def beam_axis(rot):
    """Spot lights shine along their +X (look_bench.rotator_axes = FRotationTranslationMatrix)."""
    return tuple(lb.rotator_axes(rot["yaw"], rot["pitch"], rot["roll"])[0])


def rot_from_axis(u):
    """Rotator whose +X is u (roll 0)."""
    return {"roll": 0.0, "pitch": math.degrees(math.asin(max(-1.0, min(1.0, u[2])))),
            "yaw": math.degrees(math.atan2(u[1], u[0]))}


def rot_plane_facing(u):
    """Rotator whose +Z is u (the engine Plane's normal), roll 0: pitch = pitch(u) - 90, yaw = yaw(u)."""
    r = rot_from_axis(u)
    return {"roll": 0.0, "pitch": r["pitch"] - 90.0, "yaw": r["yaw"]}


def cone_basis(u):
    """h: horizontal, perpendicular to the beam; v = h x u: 'up' across the beam."""
    h = vcross(u, (0.0, 0.0, 1.0))
    if math.sqrt(vdot(h, h)) < 1e-6:            # a vertical beam: any horizontal axis
        h = (1.0, 0.0, 0.0)
    h = vunit(h)
    return h, vunit(vcross(h, u))


def heading(pose):
    yaw = math.radians(float(pose["rot"]["yaw"]))
    return (math.cos(yaw), math.sin(yaw), 0.0), (-math.sin(yaw), math.cos(yaw), 0.0)


def ahead_of(pose, loc):
    """Signed distance of loc in front of the camera along its heading (horizontal)."""
    fwd, _r = heading(pose)
    return vdot(vsub((loc[0], loc[1], 0.0), (pose["loc"][0], pose["loc"][1], 0.0)), fwd)


def route_crossing(pose, beam_loc, u):
    """Distance along the beam where it crosses the camera's route line (the vertical plane through the camera
    along its heading). None when the beam runs parallel to the route or crosses behind the lamp."""
    _f, right = heading(pose)
    lat0 = vdot(vsub(beam_loc, pose["loc"]), right)
    du = vdot(u, right)
    if abs(du) < 1e-3:
        return None
    s = -lat0 / du
    return s if s > 0.0 else None


def beam_span(pose, beam, p):
    """(s0, s1): the analysed stretch of the beam. s0 skips the occluder zone (identical for every variant, so
    the masks match); s1 = min(attenuation, route crossing + mask_past_route_cm)."""
    u = beam_axis(beam["rotation"])
    s0 = float(p["a_occ_distance_cm"]) + float(p["mask_start_extra_cm"])
    cross = route_crossing(pose, beam["location"], u)
    s1 = float(beam["attenuation_cm"])
    if cross is not None:
        s1 = min(s1, cross + float(p["mask_past_route_cm"]))
    return s0, max(s0 + 1.0, s1), cross


def project_px(pose, pt, w, h):
    got = lb.project(dict(pose, aspect=float(w) / float(h)), tuple(pt))
    if got is None:
        return None
    nx, ny, depth = got
    return (nx + 1.0) * 0.5 * w, (1.0 - ny) * 0.5 * h, depth


def mask_spec(pose, beam, p, w, h):
    """Discs along the beam core in pixel units of a w x h frame: [(x, y, r_px), ...]."""
    u = beam_axis(beam["rotation"])
    s0, s1, cross = beam_span(pose, beam, p)
    tan_c = math.tan(math.radians(float(beam["outer_cone_deg"])))
    th = math.tan(math.radians(float(pose["fov_deg"])) / 2.0)
    n = max(2, int(p["mask_samples"]))
    discs = []
    for i in range(n):
        s = s0 + (s1 - s0) * i / float(n - 1)
        got = project_px(pose, vadd(beam["location"], vmul(u, s)), w, h)
        if got is None:
            continue
        x, y, depth = got
        r_px = float(p["mask_core"]) * s * tan_c / depth / th * (w / 2.0)
        discs.append((round(x, 3), round(y, 3), round(max(r_px, 0.5), 3)))
    return {"w": int(w), "h": int(h), "discs": discs, "s0": s0, "s1": s1, "route_cross_s": cross}


def mask_grid(spec, gw, gh):
    """Boolean mask (row-major lists) at gw x gh from a mask_spec made at spec['w'] x spec['h']."""
    sx, sy = gw / float(spec["w"]), gh / float(spec["h"])
    rows = [[False] * gw for _ in range(gh)]
    for x, y, r in spec["discs"]:
        cx, cy, rr = x * sx, y * sy, max(r * sx, 0.5)
        for j in range(max(0, int(cy - rr) - 1), min(gh, int(cy + rr) + 2)):
            for i in range(max(0, int(cx - rr) - 1), min(gw, int(cx + rr) + 2)):
                if (i + 0.5 - cx) ** 2 + (j + 0.5 - cy) ** 2 <= rr * rr:
                    rows[j][i] = True
    return rows


def mask_fraction(rows):
    n = sum(len(r) for r in rows)
    return sum(sum(1 for v in r if v) for r in rows) / float(n) if n else 0.0


def box_blur(rows, r):
    """Separable box blur with clamped edges (integral sums). rows: h lists of w floats."""
    r = max(1, int(r))

    def blur_line(line):
        n = len(line)
        acc = [0.0]
        for v in line:
            acc.append(acc[-1] + v)
        out = []
        for i in range(n):
            a, b = max(0, i - r), min(n, i + r + 1)
            out.append((acc[b] - acc[a]) / float(b - a))
        return out
    horiz = [blur_line(line) for line in rows]
    cols = [blur_line([horiz[j][i] for j in range(len(horiz))]) for i in range(len(horiz[0]))]
    return [[cols[i][j] for i in range(len(cols))] for j in range(len(horiz))]


def texture_metric(luma, mask, blur_px):
    """Inside the mask: mean luma, std, and the std of the high-passed luma (luma - box blur) = 'texture';
    hp_rel = hp_std / max(mean, 1). A smooth shaft (any slow gradient) has a small hp_std."""
    blur = box_blur(luma, blur_px)
    vals, hp = [], []
    for j, row in enumerate(luma):
        for i, v in enumerate(row):
            if mask[j][i]:
                vals.append(v)
                hp.append(v - blur[j][i])
    if not vals:
        return {"n": 0, "mean": None, "std": None, "hp_std": None, "hp_rel": None}
    n = float(len(vals))
    mean = sum(vals) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
    hm = sum(hp) / n
    hp_std = math.sqrt(sum((v - hm) ** 2 for v in hp) / n)
    return {"n": len(vals), "mean": mean, "std": std, "hp_std": hp_std, "hp_rel": hp_std / max(mean, 1.0)}


def texture_verdict(base, var, p):
    """'textured' = hp_rel >= textured_ratio x base's AND mean >= keep_brightness x base's. base vs base is the
    failing control (ratio 1.0)."""
    ratio_k, keep = float(p.get("textured_ratio", 1.25)), float(p.get("keep_brightness", 0.25))
    if not base or not var or not base.get("n") or not var.get("n"):
        return {"textured": None, "why": "no mask pixels"}
    ratio = var["hp_rel"] / max(base["hp_rel"], 1e-6)
    kept = var["mean"] / max(base["mean"], 1e-6)
    return {"textured": ratio >= ratio_k and kept >= keep, "ratio": ratio, "kept": kept,
            "why": "ok" if ratio >= ratio_k and kept >= keep else ("beam lost" if kept < keep else "no more texture")}


def cone_rays(beam, p, length):
    """Trace fan: centre + rings (fraction of the outer cone, count). -> [(start, end), ...]."""
    u = beam_axis(beam["rotation"])
    h, v = cone_basis(u)
    c = math.radians(float(beam["outer_cone_deg"]))
    start = vadd(beam["location"], vmul(u, float(p["a_trace_start_cm"])))
    dirs = [u]
    for frac, count in p["a_trace_rings"]:
        a = c * float(frac)
        for k in range(int(count)):
            phi = 2.0 * math.pi * k / float(count)
            d = vadd(vmul(u, math.cos(a)), vadd(vmul(h, math.sin(a) * math.cos(phi)), vmul(v, math.sin(a) * math.sin(phi))))
            dirs.append(vunit(d))
    return [(start, vadd(beam["location"], vmul(d, float(length)))) for d in dirs]


def classify_occlusion(hits, control_hit, p):
    """hits: per ray None or {"dist", "label", ...}. control_hit: the camera's downward trace (positive control)."""
    if control_hit is None:
        return {"verdict": "blind", "blocked_frac": None, "labels": [],
                "why": "positive control (trace down from the camera) hit nothing: traces cannot see this world"}
    n = len(hits)
    blocked = [x for x in hits if x is not None]
    f = len(blocked) / float(n) if n else 0.0
    labels = sorted({x["label"] for x in blocked})
    if f < float(p["a_clear_max_frac"]):
        verdict = "clear"
    elif f > float(p["a_blocked_min_frac"]):
        verdict = "blocked"
    else:
        verdict = "partial"
    return {"verdict": verdict, "blocked_frac": f, "labels": labels,
            "nearest_cm": min((x["dist"] for x in blocked), default=None)}


def occluder_needed(occ, p):
    pol = p["a_occluder_policy"]
    if pol == "always":
        return True
    if pol == "never":
        return False
    return occ["verdict"] in ("clear", "blind")


def behind_wing_advice(occ, meshes, beam, cross, p):
    """Advisory, [inferred: component BOUNDS boxes, not shapes]: is a wing-like mesh between the lamp and the
    route? If the beam is clear, which nearby mesh could it be moved behind (lamp a_behind_cm behind the mesh centre
    along the beam)? If blocked, the lamp needs moving in front of the blocker."""
    u = beam_axis(beam["rotation"])
    span = cross if cross is not None else float(beam["attenuation_cm"])
    rows = []
    for m in meshes:
        d = vsub(m["center"], beam["location"])
        along = vdot(d, u)
        perp = math.sqrt(max(0.0, vdot(d, d) - along * along))
        rows.append(dict(m, along=along, perp=perp))
    between = [r for r in rows if 0.0 < r["along"] < span and r["perp"] <= max(r["extent"]) + 50.0]
    wings = sorted((r for r in rows if "wing" in (r["label"] + r.get("component", "")).lower()),
                   key=lambda r: math.dist(r["center"], beam["location"]))
    out = {"verdict": occ["verdict"], "between_by_bounds": [r["label"] + "/" + r.get("component", "")
                                                            for r in sorted(between, key=lambda r: r["along"])][:8]}
    if occ["verdict"] == "blocked":
        out["advice"] = "the beam is cut before the route: with shadows ON it dies; move the lamp in front of %s" % (
            ", ".join(occ["labels"][:3]) or "the blocker")
        out["needs_move"] = True
    elif occ["verdict"] in ("clear", "blind") and wings:
        w = wings[0]
        new = vsub(w["center"], vmul(u, float(p["a_behind_cm"])))
        out.update(needs_move=True, candidate=w["label"] + "/" + w.get("component", ""),
                   move_lamp_to=[round(x, 1) for x in new],
                   advice="no wing in the beam: for natural shafts move the lamp behind the nearest wing "
                          "(%s), ~%.0f cm behind its centre along the beam" % (w["label"], float(p["a_behind_cm"])))
    elif occ["verdict"] == "partial":
        out.update(needs_move=False, advice="a pierced wing / the rig already cuts the beam: shadows alone should "
                                            "make shafts; no ZZ_ occluder needed")
    else:
        out.update(needs_move=None, advice="no wing-like mesh found near the lamp")
    return out


def bar_specs(beam, p):
    u = beam_axis(beam["rotation"])
    h, v = cone_basis(u)
    d = float(p["a_occ_distance_cm"])
    r = d * math.tan(math.radians(float(beam["outer_cone_deg"])))
    n = int(p["a_bar_count"])
    pitch = 2.0 * r / float(n)                   # bars across the cone diameter, equal gaps
    centre = vadd(beam["location"], vmul(u, d))
    length = max(2.0 * r * float(p["a_bar_len_k"]), 20.0)
    t = float(p["a_bar_thick_cm"])
    rot = rot_from_axis(h)                       # bar long axis (+X) along h, square section
    out = []
    for k in range(n):
        off = (k - (n - 1) / 2.0) * pitch
        out.append({"label": PREFIX + "BAR_%d" % k, "kind": "mesh", "loc": vadd(centre, vmul(v, off)),
                    "rot": rot, "scale": (length / 100.0, t / 100.0, t / 100.0)})
    return out, {"cone_radius_cm": r, "pitch_cm": pitch, "duty": t / pitch if pitch else None}


def breakup_spec(beam, p):
    u = beam_axis(beam["rotation"])
    d = float(p["a_occ_distance_cm"])
    r = d * math.tan(math.radians(float(beam["outer_cone_deg"])))
    s = max(2.0 * r * float(p["a_breakup_size_k"]), 20.0) / 100.0
    return [{"label": PREFIX + "BREAKUP", "kind": "mesh", "loc": vadd(beam["location"], vmul(u, d)),
             "rot": rot_plane_facing(u), "scale": (s, s, 1.0)}]


def noisebox_spec(pose, beam, p):
    u = beam_axis(beam["rotation"])
    s0, s1, _cross = beam_span(pose, beam, p)
    r1 = s1 * math.tan(math.radians(float(beam["outer_cone_deg"])))
    side = 2.0 * (r1 + float(p["b_box_margin_cm"]))
    mid = vadd(beam["location"], vmul(u, 0.5 * (s0 + s1)))
    return [{"label": PREFIX + "NOISEBOX", "kind": "mesh", "loc": mid, "rot": rot_from_axis(u),
             "scale": ((s1 - s0) / 100.0, side / 100.0, side / 100.0)}]


def lcg(seed):
    state = [int(seed) & 0x7FFFFFFF or 1]

    def nxt():
        state[0] = (1103515245 * state[0] + 12345) & 0x7FFFFFFF
        return state[0] / float(0x7FFFFFFF)
    return nxt


def clump_specs(pose, beam, p):
    """Deterministic (seeded LCG: never two draws in one expression) LFV clumps along the beam."""
    u = beam_axis(beam["rotation"])
    h, v = cone_basis(u)
    s0, s1, _cross = beam_span(pose, beam, p)
    rnd = lcg(p["bl_seed"])
    out = []
    for k in range(int(p["bl_count"])):
        t = rnd()
        rad = float(p["bl_radius_min_cm"]) + (float(p["bl_radius_max_cm"]) - float(p["bl_radius_min_cm"])) * rnd()
        ext = float(p["bl_ext_min"]) + (float(p["bl_ext_max"]) - float(p["bl_ext_min"])) * rnd()
        jh = (rnd() - 0.5) * rad
        jv = (rnd() - 0.5) * rad
        s = s0 + (s1 - s0) * (k + t) / float(int(p["bl_count"]))
        loc = vadd(vadd(beam["location"], vmul(u, s)), vadd(vmul(h, jh), vmul(v, jv)))
        out.append({"label": PREFIX + "CLUMP_%d" % k, "kind": "fog", "loc": loc, "yaw": 0.0,
                    "scale": rad / 500.0, "radial": ext, "height": 0.0, "falloff": 1.0, "offset": 0.0,
                    "phase_g": float(p["bl_phase_g"])})
    return out


def d_cvar_targets(live, p):
    """-> {name: {"live", "target", "escalated", "noop"}}. Escalation when the base already meets the brief:
    GridPixelSize halves (min 2), GridSizeZ doubles (max 256), HistoryWeight -0.2 (min 0.3)."""
    out = {}
    for name, want in sorted(p["d_cvars"].items()):
        now = live.get(name)
        want = float(want)
        esc = False
        if now is None:
            out[name] = {"live": None, "target": want, "escalated": False, "noop": False}
            continue
        now = float(now)
        if name.endswith("GridPixelSize"):
            if now <= want:
                want, esc = (max(2.0, math.floor(now / 2.0)), True) if p["d_escalate"] else (now, False)
        elif name.endswith("GridSizeZ"):
            if now >= want:
                want, esc = (min(256.0, now * 2.0), True) if p["d_escalate"] else (now, False)
        elif name.endswith("HistoryWeight"):
            if now <= want:
                want, esc = (max(0.3, round(now - 0.2, 3)), True) if p["d_escalate"] else (now, False)
        out[name] = {"live": now, "target": want, "escalated": esc, "noop": abs(want - now) < 1e-6}
    return out


def plan_a(beam, occ, p):
    ops = [op("light", beam["id"], "cast_shadows", True), op("light", beam["id"], "cast_volumetric_shadow", True)]
    pool, info = [], {"occlusion": occ["verdict"], "blocked_frac": occ.get("blocked_frac"),
                      "occluder": None, "shadows_were": [beam["cast_shadows"], beam["cast_volumetric_shadow"]]}
    if occluder_needed(occ, p):
        if p["a_occluder"] == "breakup":
            pool = breakup_spec(beam, p)
        else:
            pool, geo = bar_specs(beam, p)
            info["bars"] = geo
        info["occluder"] = p["a_occluder"]
    return {"ops": ops, "pool": pool, "info": info}


def fog_scale_ops(fogs, p):
    k = float(p["b_fog_density_scale"])
    ops = []
    for f in sorted(fogs, key=lambda f: f["id"]):
        ops.append(op("fog", f["id"], "fog_density", float(f["fog_density"]) * k))
        ops.append(op("fog", f["id"], "second_fog_density", float(f["second_fog_density"]) * k))
    return ops


def plan_b(pose, beam, fogs, p):
    return {"ops": fog_scale_ops(fogs, p), "pool": noisebox_spec(pose, beam, p),
            "info": {"fogs": len(fogs), "fog_scale": float(p["b_fog_density_scale"]), "material": MAT_NOISE,
                     "extinction_peak_per_m": float(p["b_extinction_peak"]), "noise_cm": float(p["b_noise_cm"])}}


def plan_bl(pose, beam, fogs, p):
    pool = clump_specs(pose, beam, p)
    return {"ops": fog_scale_ops(fogs, p), "pool": pool,
            "info": {"fogs": len(fogs), "clumps": len(pool), "fog_scale": float(p["b_fog_density_scale"])}}


def plan_d(fogs, cvars_live, p):
    tg = d_cvar_targets(cvars_live, p)
    ops = [op("cvar", n, "value", t["target"]) for n, t in sorted(tg.items()) if not t["noop"]]
    for f in sorted(fogs, key=lambda f: f["id"]):
        ops.append(op("fog", f["id"], "scattering_distribution", float(p["d_scattering_distribution"])))
    return {"ops": ops, "pool": [], "info": {"cvars": tg, "escalated": sorted(n for n, t in tg.items() if t["escalated"]),
                                             "noop": sorted(n for n, t in tg.items() if t["noop"]),
                                             "scattering_distribution": float(p["d_scattering_distribution"]),
                                             "scattering_was": [f["scattering_distribution"] for f in fogs]}}


VARIANT_PARTS = {"base": (), "A": ("A",), "B": ("B",), "BL": ("BL",), "D": ("D",), "ALL": ("A", "B", "D")}


def variant_plan(name, plans):
    ops, pool = [], []
    for part in VARIANT_PARTS[name]:
        ops += plans[part]["ops"]
        pool += plans[part]["pool"]
    seen = {}
    for o in ops:
        k = key(o[0], o[1], o[2])
        if k in seen and plain(seen[k]) != plain(o[3]):
            raise RuntimeError("%s_CONFLICT|%s|%s" % (MARK, name, k))
        seen[k] = o[3]
    labels = [s["label"] for s in pool]
    if len(set(labels)) != len(labels):
        raise RuntimeError("%s_POOL_CONFLICT|%s" % (MARK, name))
    return ops, pool


def all_keys(plans):
    keys = set()
    for name in ORDER:
        ops, _pool = variant_plan(name, plans)
        keys.update(key(o[0], o[1], o[2]) for o in ops)
    return sorted(keys)


def position_tasks(variants, dry=False):
    """Per position: locate (scrubs), repose, base settle, plan, base timing, base stills, then per variant a base
    return (after any change), apply, settle, hold check, timing, stills; a final base return."""
    tasks = [("locate",), ("repose",), ("settle", "base_ref"), ("plan",), ("time", "base"), ("shoot", "base")]
    if dry:
        return tasks
    changed = False
    for v in variants:
        if v == "base":
            continue
        if changed:
            tasks.append(("settle", "base_return"))
        tasks += [("apply", v), ("settle", "state"), ("hold", v), ("time", v), ("shoot", v)]
        changed = True
    if changed:
        tasks.append(("settle", "base_return_final"))
    return tasks


def locate_next(samples, target, p, bay_count):
    """samples: [(fraction, ahead_cm), ...] in scrub order. -> (fraction, done, best). The camera moves forward as
    the fraction grows, so ahead_cm falls. First (or non-monotonic) step: locate_first_step_bays bays toward the
    target; then secant on the last two distinct samples, each step capped at locate_max_step_bays; [0, 1]."""
    best = min(samples, key=lambda s: abs(s[1] - target))
    if abs(best[1] - target) <= float(p["locate_tol_cm"]):
        return best[0], True, best
    if len(samples) >= int(p["locate_max_iter"]):
        return best[0], True, best
    f1, a1 = samples[-1]
    fixed = float(p["locate_first_step_bays"]) / float(bay_count)
    cap = float(p.get("locate_max_step_bays", 3.0)) / float(bay_count)
    prior = [s for s in samples[:-1] if abs(s[0] - f1) > 1e-9 and abs(s[1] - a1) > 1e-6]
    step = None
    if prior:
        f0, a0 = prior[-1]
        slope = (f1 - f0) / (a1 - a0)            # fraction per cm (negative when the camera advances)
        if slope < 0.0:
            step = (target - a1) * slope
    if step is None:
        step = fixed if a1 > target else -fixed  # lamp too far ahead -> move the camera forward
    step = max(-cap, min(cap, step))
    return max(0.0, min(1.0, f1 + step)), False, best


def compile_errors_since(log_text, marker, names):
    """Lines after the LAST line holding `marker` that report a compile failure for any of `names` (asset short
    names). None when the marker is absent (cannot judge). s3_marble_tiling_material.py:311-323 pattern."""
    lines = log_text.splitlines()
    start = max((i for i, ln in enumerate(lines) if marker in ln), default=-1)
    if start < 0:
        return None
    short = [n.rsplit("/", 1)[-1] for n in names]
    return [ln for ln in lines[start + 1:]
            if any(s in ln for s in short) and ("failed to compile" in ln.lower() or "error" in ln.lower())]


# 3-octave 3D value noise, the 2D construction of s3_marble_tiling_material.py:351-366 lifted to 3D (each corner
# wrapped at 289 separately). Keep in step with noise3_reference() (harness).
CODE_NOISE3 = r"""
float3 q = (WP + float3(Drift * T, 0.37 * Drift * T, 0.0)) / max(NoiseCm, 1.0);
float n = 0.0;
float amp = 0.6;
float norm = 0.0;
for (int o = 0; o < 3; o++)
{
    float3 c0 = floor(q);
    float3 f = q - c0;
    float3 u = f * f * (3.0 - 2.0 * f);
    float3 c1 = c0 + 1.0;
    c0 = c0 - 289.0 * floor(c0 / 289.0);
    c1 = c1 - 289.0 * floor(c1 / 289.0);
    float3 k = float3(127.1, 311.7, 74.7);
    float h000 = frac(sin(dot(float3(c0.x, c0.y, c0.z), k)) * 43758.5453);
    float h100 = frac(sin(dot(float3(c1.x, c0.y, c0.z), k)) * 43758.5453);
    float h010 = frac(sin(dot(float3(c0.x, c1.y, c0.z), k)) * 43758.5453);
    float h110 = frac(sin(dot(float3(c1.x, c1.y, c0.z), k)) * 43758.5453);
    float h001 = frac(sin(dot(float3(c0.x, c0.y, c1.z), k)) * 43758.5453);
    float h101 = frac(sin(dot(float3(c1.x, c0.y, c1.z), k)) * 43758.5453);
    float h011 = frac(sin(dot(float3(c0.x, c1.y, c1.z), k)) * 43758.5453);
    float h111 = frac(sin(dot(float3(c1.x, c1.y, c1.z), k)) * 43758.5453);
    float y0 = lerp(lerp(h000, h100, u.x), lerp(h010, h110, u.x), u.y);
    float y1 = lerp(lerp(h001, h101, u.x), lerp(h011, h111, u.x), u.y);
    n += amp * lerp(y0, y1, u.z);
    norm += amp;
    q = q * 2.03 + float3(17.1, 5.3, 11.7);
    amp *= 0.5;
}
n /= norm;
float d = saturate((n - 0.5) * Contrast + 0.5);
return Peak * lerp(FloorFrac, 1.0, d);
"""
NOISE_INPUTS = ["WP", "T", "NoiseCm", "Contrast", "FloorFrac", "Peak", "Drift"]
NOISE_PARAMS = {"NoiseCm": "b_noise_cm", "Contrast": "b_noise_contrast", "FloorFrac": "b_noise_floor",
                "Peak": "b_extinction_peak", "Drift": "b_drift_cm_s"}

CODE_BREAKUP = r"""
return saturate((X - Thr) * Contrast + 0.5);
"""


def _h3(c):
    return (math.sin(c[0] * 127.1 + c[1] * 311.7 + c[2] * 74.7) * 43758.5453) % 1.0


def noise3_reference(wp, t, p):
    """Python mirror of CODE_NOISE3 (same order of operations)."""
    drift = float(p["b_drift_cm_s"])
    nc = max(float(p["b_noise_cm"]), 1.0)
    q = [(wp[0] + drift * t) / nc, (wp[1] + 0.37 * drift * t) / nc, wp[2] / nc]
    n, amp, norm = 0.0, 0.6, 0.0
    for _ in range(3):
        c0 = [math.floor(x) for x in q]
        f = [q[i] - c0[i] for i in range(3)]
        u = [x * x * (3.0 - 2.0 * x) for x in f]
        c1 = [x + 1.0 for x in c0]
        c0 = [x - 289.0 * math.floor(x / 289.0) for x in c0]
        c1 = [x - 289.0 * math.floor(x / 289.0) for x in c1]
        hv = {}
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    hv[(a, b, c)] = _h3((c1[0] if a else c0[0], c1[1] if b else c0[1], c1[2] if c else c0[2]))
        lerp = lambda x, y, s: x + (y - x) * s
        y0 = lerp(lerp(hv[0, 0, 0], hv[1, 0, 0], u[0]), lerp(hv[0, 1, 0], hv[1, 1, 0], u[0]), u[1])
        y1 = lerp(lerp(hv[0, 0, 1], hv[1, 0, 1], u[0]), lerp(hv[0, 1, 1], hv[1, 1, 1], u[0]), u[1])
        n += amp * lerp(y0, y1, u[2])
        norm += amp
        q = [q[0] * 2.03 + 17.1, q[1] * 2.03 + 5.3, q[2] * 2.03 + 11.7]
        amp *= 0.5
    n /= norm
    d = min(1.0, max(0.0, (n - 0.5) * float(p["b_noise_contrast"]) + 0.5))
    return float(p["b_extinction_peak"]) * (float(p["b_noise_floor"]) + (1.0 - float(p["b_noise_floor"])) * d)


# Python names of every UFUNCTION / class the PIE adapter calls (hasattr at arm, before any change).
PIE_API = (
    ("GameplayStatics", ("get_all_actors_of_class", "get_player_camera_manager")),
    ("PlayerCameraManager", ("get_camera_location", "get_camera_rotation", "get_fov_angle")),
    ("Actor", ("get_component_by_class", "get_components_by_class", "get_actor_label", "actor_has_tag",
               "set_actor_location_and_rotation", "set_actor_scale3d", "set_actor_hidden_in_game",
               "get_actor_location")),
    ("SceneComponent", ("get_world_location", "get_world_rotation", "is_visible", "set_visibility")),
    ("LightComponentBase", ("set_cast_shadows", "set_cast_volumetric_shadow")),   # LightComponentBase.h:146, :153
    ("ExponentialHeightFogComponent", ("set_fog_density", "set_second_fog_density",
                                       "set_volumetric_fog_scattering_distribution")),  # ...FogComponent.h:251-308
    ("LocalFogVolumeComponent", ("set_radial_fog_extinction", "set_height_fog_extinction", "set_height_fog_falloff",
                                 "set_height_fog_offset", "set_fog_phase_g")),   # LocalFogVolumeComponent.h:55-64
    ("SystemLibrary", ("execute_console_command", "get_console_variable_float_value", "line_trace_single",
                       "get_component_bounds")),     # KismetSystemLibrary.h:604, :622, :1270
    ("SpotLightComponent", ()), ("LocalLightComponent", ()), ("StaticMeshComponent", ()), ("StaticMeshActor", ()),
    ("ExponentialHeightFog", ()), ("LocalFogVolume", ()), ("PostProcessVolume", ()), ("InfinityStageShowRoot", ()),
    ("TraceTypeQuery", ()), ("DrawDebugTrace", ()),
)
EDITOR_API = (
    ("EditorActorSubsystem", ("spawn_actor_from_class", "destroy_actor")),
    ("MaterialEditingLibrary", ("create_material_expression", "connect_material_expressions",
                                "connect_material_property", "recompile_material",
                                "get_material_expressions")),           # MaterialEditingLibrary.h:168, :232
    ("EditorAssetLibrary", ("does_asset_exist",)),
    ("AssetToolsHelpers", ("get_asset_tools",)),
    ("MaterialFactoryNew", ()), ("Material", ()),
    ("MaterialExpressionCustom", ()), ("MaterialExpressionWorldPosition", ()), ("MaterialExpressionTruncateLWC", ()),
    ("MaterialExpressionTime", ()), ("MaterialExpressionScalarParameter", ()),
    ("MaterialExpressionConstant3Vector", ()), ("MaterialExpressionTextureCoordinate", ()),
    ("MaterialExpressionTextureSample", ()), ("CustomInput", ()),
    ("MaterialDomain", ("MD_VOLUME",)), ("BlendMode", ("BLEND_ADDITIVE", "BLEND_MASKED", "BLEND_OPAQUE")),
    ("MaterialShadingModel", ("MSM_DEFAULT_LIT", "MSM_UNLIT")),
    ("MaterialProperty", ("MP_BASE_COLOR", "MP_SUBSURFACE_COLOR", "MP_EMISSIVE_COLOR", "MP_OPACITY_MASK")),
    ("StaticMeshActor", ()), ("LocalFogVolume", ()), ("LocalFogVolumeComponent", ()),
)


def api_missing(unreal, table=PIE_API):
    return fb.api_missing(unreal, table, ())


def pool_specs_template(p):
    """Every pool label any variant can show (PREPARE spawns them all, hidden)."""
    rows = [{"label": PREFIX + "BAR_%d" % k, "kind": "mesh", "mesh": CUBE, "material": MAT_BLACK, "cast_shadow": True}
            for k in range(int(p["a_bar_count"]))]
    rows.append({"label": PREFIX + "BREAKUP", "kind": "mesh", "mesh": PLANE, "material": MAT_BREAKUP,
                 "cast_shadow": True})
    rows.append({"label": PREFIX + "NOISEBOX", "kind": "mesh", "mesh": CUBE, "material": MAT_NOISE,
                 "cast_shadow": False})
    rows += [{"label": PREFIX + "CLUMP_%d" % k, "kind": "fog"} for k in range(int(p["bl_count"]))]
    return rows


def pool_labels_needed(p):
    return [r["label"] for r in pool_specs_template(p)]


# --------------------------------------------------------------------------
# engine-free bench: originals, apply, hold, restore, verify (adapter injected)
# --------------------------------------------------------------------------

class BeamBench:
    """Never spawns or destroys: changes properties / cvars of existing PIE objects and places, shows and hides
    the PREPAREd ZZ_BEAMTEX_ pool."""

    def __init__(self, adapter, record_path, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or ("BEAMTEX-" + utc_stamp())
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
        if not self.applied:
            return []
        out = []
        tol = float(self.p["rot_tol_deg"])
        for kind, oid, field, value in self.applied[1]:
            if not same_value(field, self.a.read(kind, oid, field), value, tol):
                out.append(key(kind, oid, field))
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
    bench = BeamBench(adapter, record_path, record.get("params"), record.get("run"))
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
# PREPARE (editor world, PIE not running): bench materials (create-only) + the hidden ZZ_BEAMTEX_* pool
# --------------------------------------------------------------------------

class PrepareBench:
    def __init__(self, adapter, record_path, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or ("BEAMTEXPREP-" + utc_stamp())
        self.record = None

    def run(self):
        kind = self.a.world_kind()
        if kind != "editor":
            raise BenchRefused("prepare_needs_editor", "world=%s; end PIE first" % kind, self.run_id)
        missing = self.a.api_missing()
        if missing:
            raise BenchRefused("api_missing", ",".join(missing), self.run_id)
        census = self.a.census()
        if census["maps"] or census["content"]:
            raise BenchRefused("dirty_before_prepare", json.dumps(census), self.run_id)
        left = self.a.bench_actor_labels(PREFIX)
        if left:
            raise BenchRefused("leftovers", "%d %s* actors; Don't-Save restart first" % (len(left), PREFIX),
                               self.run_id)
        exist = [m for m in BENCH_MATERIALS if self.a.asset_exists(m)]
        if exist:
            raise BenchRefused("bench_assets_exist", "%s (create-only; a saved copy must be removed by hand, an "
                               "unsaved one by a Don't-Save restart)" % ",".join(exist), self.run_id)
        specs = pool_specs_template(self.p)
        self.record = {"run": self.run_id, "written_utc": utc_iso(), "world": self.a.world_name(),
                       "census_before": census, "tag": TAG, "prefix": PREFIX,
                       "pool": [s["label"] for s in specs], "materials_planned": list(BENCH_MATERIALS),
                       "materials": {}, "spawned": {}, "status": "planned", "params": plain(self.p),
                       "marker": "%s_PREPARE_MATERIALS|run=%s" % (MARK, self.run_id)}
        write_verified(self.record_path, self.record, self.a.log, self.run_id)
        self.a.note("record_written")
        self.a.log("%s_ANNOUNCE|run=%s|world=EDITOR|creating %d bench materials under %s (create-only, never "
                   "saved) and spawning %d hidden %s* actors (tag %s); they stay until a Don't-Save restart; the map "
                   "and the new packages WILL be dirty and must NOT be saved|record=%s" % (
                       MARK, self.run_id, len(BENCH_MATERIALS), ASSET_DIR, len(specs), PREFIX, TAG,
                       self.record_path.as_posix()))
        complete = False
        try:
            self.a.log(self.record["marker"])           # compile-error scan starts after this line
            self.record["substrate"] = self.a.cvar_int("r.Substrate")
            self.record["materials"] = self.a.build_materials(self.p)
            write_verified(self.record_path, self.record, self.a.log, self.run_id)
            for spec in specs:
                self.record["spawned"][spec["label"]] = self.a.spawn_hidden(spec)
            complete = True
        finally:
            after = self.a.census()
            self.record.update(status="spawned" if complete else "partial", census_after=after,
                               dirtied_by_prepare={"maps": sorted(set(after["maps"]) - set(census["maps"])),
                                                   "content": sorted(set(after["content"]) - set(census["content"]))})
            write_verified(self.record_path, self.record, self.a.log, self.run_id)
            self.a.log("%s|run=%s|editor world holds %s* actors, %s holds unsaved bench materials, the map is "
                       "dirty; Don't-Save restart, never Save All" % (RESTART, self.run_id, PREFIX, ASSET_DIR))
        present = set(self.a.pool_labels())
        labels = [s["label"] for s in specs]
        problems = []
        if present != set(labels):
            problems.append("pool mismatch missing=%s extra=%s" % (sorted(set(labels) - present),
                                                                  sorted(present - set(labels))))
        problems += ["%s not hidden" % l for l in labels if l in present and self.a.pool_state(l)["on"]]
        bad_mats = [m for m, rb in self.record["materials"].items() if not rb.get("ok")]
        if bad_mats:
            problems.append("material readback %s" % ",".join(bad_mats))
        if problems:
            raise BenchRefused("prepare_verify", ";".join(problems), self.run_id)
        self.a.log("%s_PREPARE_OK|run=%s|actors=%d|materials=%d|substrate=%s|wait ~30 s for shader compiles before "
                   "PIE; CAPTURE scans the log for compile errors|record=%s" % (
                       MARK, self.run_id, len(labels), len(self.record["materials"]), self.record["substrate"],
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


def session_records(out_root=OUT_ROOT, prepare_root=PREPARE_ROOT):
    """RESTORE's default records: only captures armed against the NEWEST PREPARE (= this editor session)."""
    found = sorted(pathlib.Path(prepare_root).glob("*/" + PREPARE_RECORD_NAME))
    if not found:
        return []
    current = json.loads(found[-1].read_text(encoding="utf-8")).get("run")
    out = []
    for path in sorted(pathlib.Path(out_root).glob("BEAMTEX-*/" + ORIGINALS_NAME)):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("prepare_run") == current:
                out.append(path)
        except ValueError:
            continue
    return out


def load_prepare_record(path):
    rec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if rec.get("status") != "spawned":
        raise BenchRefused("prepare_incomplete", "status=%s" % rec.get("status"))
    return rec


# --------------------------------------------------------------------------
# CAPTURE state machine (engine-free; Slate tick in the editor, fake clock in the harness)
# --------------------------------------------------------------------------

class BeamMachine:
    def __init__(self, bench, adapter, run, luma_reader=None):
        self.b, self.a, self.p, self.run = bench, adapter, bench.p, run
        self.read_luma = luma_reader or lb.png_luma
        self.pos_i = -1
        self.queue = []
        self.task = None
        self.sub = {}
        self.st = {"gate_failures": [], "probe_n": 0, "probe_timeouts": 0, "task_log": []}
        self.done = False
        self.pos = None
        self.last_fraction = None
        self._next_position()

    def _fail(self, why):
        self.st["gate_failures"].append(why)
        if self.pos is not None:
            self.pos.setdefault("gate_failures", []).append(why)
        self.a.log("%s_GATE|run=%s|%s" % (MARK, self.b.run_id, why))

    def _next_position(self):
        self.pos_i += 1
        if self.pos_i >= len(self.run["positions"]):
            self.done = True
            return
        self.pos = self.run["positions"][self.pos_i]
        self.pos.update(shots={}, settles=[], base_returns=[], timings={}, gate_failures=[], locate=[])
        self.queue = list(position_tasks(self.p["variants"], self.run.get("dry")))
        self.task = None

    def _scrub(self, frame):
        res = self.a.transport_scrub(int(frame))
        self.pos.setdefault("scrub_results", []).append(str(res))
        if not ps.scrub_ok(res):
            raise BenchRefused("scrub_refused", "%s frame=%d result=%s" % (self.pos["name"], int(frame), res),
                               self.b.run_id)

    def _probe(self, now, tag):
        sub = self.sub
        pend = sub.get("pending")
        if pend:
            try:
                y = float(self.read_luma(pend["path"]))
            except Exception:
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
            self._next_position()
            return
        self.task = self.queue.pop(0)
        self.sub = {"t0": now, "begun": False}
        self.st["task_log"].append([self.pos["name"]] + list(self.task))

    def step(self, now, delta=0.0):
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
        if kind == "locate":
            self._locate(now)
            return
        if kind == "repose":
            if now - sub["t0"] >= float(self.p["repose_seconds"]):
                self._scrub(self.pos["target_frame"])
                self.task = None
            return
        if kind == "settle":
            self._settle(now, t[1])
            return
        if kind == "plan":
            self._plan()
            self.task = None
            return
        if kind == "time":
            if not sub["begun"]:
                sub.update(begun=True, t0=now, deltas=[])
                return
            sub["deltas"].append(float(delta))
            if now - sub["t0"] >= float(self.p["time_seconds"]):
                fs = lb.frame_stats(sub["deltas"])
                self.pos["timings"][t[1]] = fs
                self.a.log("%s_TIME|run=%s|pos=%s|variant=%s|n=%s|p50=%s|p95=%s" % (
                    MARK, self.b.run_id, self.pos["name"], t[1], fs.get("n"),
                    "%.2f" % fs["p50"] if fs.get("n") else "none", "%.2f" % fs["p95"] if fs.get("n") else "none"))
                self.task = None
            return
        if kind == "apply":
            ops, pool = variant_plan(t[1], self.pos["_plans"])
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

    # ---- locate: secant search for the frame where the lamp is ahead_cm in front of the camera
    def _locate(self, now):
        sub, p, pos = self.sub, self.p, self.pos
        seg = self.run["segment"]
        if not sub["begun"]:
            if self.last_fraction is not None:
                f0 = self.last_fraction
            else:
                f0 = max(0.0, (int(p["bay"]) - 1) / float(p["bay_count"]))
            self.a.transport_pause()
            sub.update(begun=True, samples=[], fraction=f0, wait_until=None)
        if sub["wait_until"] is None:
            frame = ps.fraction_to_frame(seg[0], seg[1], sub["fraction"])
            self._scrub(frame)
            sub.update(frame=frame, wait_until=now + float(p["locate_wait_s"]))
            return
        if now < sub["wait_until"]:
            return
        w, h = p["resolution"]
        pose = self.a.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
        if pose is None:
            raise BenchRefused("no_camera", "no player camera manager in PIE", self.b.run_id)
        ahead = ahead_of(pose, self.run["beam"]["location"])
        sub["samples"].append((sub["fraction"], ahead))
        pos["locate"].append({"fraction": sub["fraction"], "frame": sub["frame"], "ahead_cm": round(ahead, 1)})
        nxt, done, best = locate_next(sub["samples"], float(pos["ahead_cm"]), p, p["bay_count"])
        if done:
            pos["fraction"] = best[0]
            pos["target_frame"] = ps.fraction_to_frame(seg[0], seg[1], best[0])
            pos["ahead_found_cm"] = best[1]
            self.last_fraction = best[0]
            ok = abs(best[1] - float(pos["ahead_cm"])) <= float(p["locate_tol_cm"])
            self.a.log("%s_LOCATE|run=%s|pos=%s|target_ahead=%.0f|found=%.0f|fraction=%.5f|frame=%d|iters=%d|ok=%s" % (
                MARK, self.b.run_id, pos["name"], float(pos["ahead_cm"]), best[1], best[0], pos["target_frame"],
                len(sub["samples"]), ok))
            if not ok:
                self._fail("locate %s found %.0f cm vs %.0f" % (pos["name"], best[1], float(pos["ahead_cm"])))
            self._scrub(pos["target_frame"])
            self.task = None
            return
        sub.update(fraction=nxt, wait_until=None)

    def _settle(self, now, tag):
        sub = self.sub
        if not sub["begun"]:
            if tag.startswith("base_return"):
                self.b.to_base()
            sub.update(begun=True, t0=now, samples=[], pending=None, last_issue=None)
            return
        self._probe(now, tag)
        el = now - sub["t0"]
        verdict = robust_settle(sub["samples"], el, self.p)
        if verdict == "wait":
            return
        w = int(self.p["settle_window"])
        st_now = stats([s[1] for s in sub["samples"][-w:]]) if sub["samples"] else None
        rec = {"kind": tag, "verdict": verdict, "seconds": round(el, 3), "stats": st_now,
               "after": self.pos.get("_last_variant", "base"), "samples": sub["samples"]}
        self.pos["settles"].append(rec)
        self.a.log("%s_SETTLE|run=%s|pos=%s|kind=%s|verdict=%s|median=%s|seconds=%.1f" % (
            MARK, self.b.run_id, self.pos["name"], tag, verdict,
            "%.1f" % st_now["median"] if st_now else "none", el))
        if verdict != "stable":
            self._fail("settle %s/%s/%s" % (self.pos["name"], tag, rec["after"]))
        if tag == "base_ref":
            self.pos["base_ref"] = st_now
        elif tag.startswith("base_return") and st_now and self.pos.get("base_ref"):
            ok, tol = base_return_ok(st_now, self.pos["base_ref"], self.p)
            self.pos["base_returns"].append({"after": rec["after"], "median": st_now["median"],
                                             "ref": self.pos["base_ref"]["median"], "tol": tol, "ok": ok})
            self.a.log("%s_BASE_RETURN|run=%s|pos=%s|after=%s|median=%.1f|ref=%.1f|tol=%.1f|ok=%s" % (
                MARK, self.b.run_id, self.pos["name"], rec["after"], st_now["median"],
                self.pos["base_ref"]["median"], tol, ok))
            if not ok:
                self._fail("base_return %s after %s %.1f vs %.1f" % (self.pos["name"], rec["after"],
                                                                      st_now["median"], self.pos["base_ref"]["median"]))
        self.task = None

    def _plan(self):
        a, p, pos = self.a, self.p, self.pos
        w, h = p["resolution"]
        pose = a.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
        if pose is None:
            raise BenchRefused("no_camera", "no player camera manager in PIE", self.b.run_id)
        beam = a.beam_rows(self.run["beam_regex"])
        if len(beam) != 1:
            raise BenchRefused("beam_lost", "%d rows for %s" % (len(beam), self.run["beam_regex"]), self.b.run_id)
        beam = beam[0]
        struck = float(beam["intensity"]) >= float(p["struck_min_intensity"])
        spec = mask_spec(pose, beam, p, w, h)
        gw, gh = p["mask_grid"]
        frac = mask_fraction(mask_grid(spec, gw, gh))
        u = beam_axis(beam["rotation"])
        _s0, s1, cross = beam_span(pose, beam, p)
        rays = cone_rays(beam, p, cross if cross is not None else float(beam["attenuation_cm"]))
        hits = [a.trace(s, e, beam["actor_id"]) for s, e in rays]
        drop = (pose["loc"][0], pose["loc"][1], pose["loc"][2] - float(p["a_control_drop_cm"]))
        control = a.trace(tuple(pose["loc"]), drop, beam["actor_id"])
        occ = classify_occlusion(hits, control, p)
        meshes = a.meshes_near(beam["location"], float(p["a_wing_radius_cm"]), int(p["a_wing_max_rows"]),
                               float(p["a_wing_max_extent_cm"]))
        advice = behind_wing_advice(occ, meshes, beam, cross, p)
        fogs = a.fogs()
        cvars_live = {n: a.cvar(n) for n in sorted(p["d_cvars"])}
        plans = {"A": plan_a(beam, occ, p), "B": plan_b(pose, beam, fogs, p), "BL": plan_bl(pose, beam, fogs, p),
                 "D": plan_d(fogs, cvars_live, p)}
        pos["_plans"] = plans
        summary = {v: plans[v]["info"] for v in ("A", "B", "BL", "D")}
        summary.update(pose=pose, beam=beam, struck=struck, mask=spec, mask_frac=frac, beam_axis=u,
                       route_cross_s=cross, occlusion=dict(occ, rays=len(rays), control=control is not None),
                       behind_wing=advice, exposure=self.run.get("exposure"),
                       ahead_at_plan=ahead_of(pose, beam["location"]), frame=a.transport_frame())
        if self.run.get("dry"):
            self.b.record_keys([], pos["name"], summary)
        else:
            self.b.record_keys(all_keys(plans), pos["name"], summary)   # originals on disk BEFORE any change here
        pos["plan"] = summary
        a.log("%s_PLAN|run=%s|pos=%s|ahead=%.0f|struck=%s|intensity=%.1f|mask_frac=%.4f|route_cross=%s|cam=%.0f,%.0f,"
              "%.0f|yaw=%.1f" % (MARK, self.b.run_id, pos["name"], summary["ahead_at_plan"], struck,
                                 float(beam["intensity"]), frac, "%.0f" % cross if cross is not None else "none",
                                 pose["loc"][0], pose["loc"][1], pose["loc"][2], pose["rot"]["yaw"]))
        a.log("%s_OCCLUSION|run=%s|pos=%s|verdict=%s|blocked=%s|labels=%s|advice=%s" % (
            MARK, self.b.run_id, pos["name"], occ["verdict"], occ.get("blocked_frac"), ",".join(occ["labels"][:4]),
            advice.get("advice", "")[:160]))
        for v in ("A", "B", "BL", "D"):
            a.log("%s_PLAN|run=%s|pos=%s|variant=%s|ops=%d|pool=%d|info=%s" % (
                MARK, self.b.run_id, pos["name"], v, len(plans[v]["ops"]), len(plans[v]["pool"]),
                json.dumps(plain(plans[v]["info"]), sort_keys=True)[:400]))
        if not struck:
            self._fail("unstruck %s intensity %.2f" % (pos["name"], float(beam["intensity"])))
        if frac < float(p["mask_min_frac"]):
            self._fail("beam_not_in_shot %s mask_frac %.4f" % (pos["name"], frac))

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
            rows = a.beam_rows(self.run["beam_regex"])
            inten = float(rows[0]["intensity"]) if len(rows) == 1 else None
            a.console('HighResShot %dx%d filename="%s"' % (w, h, path.as_posix()))
            shot["stills"].append({"i": sub["i"], "path": path.as_posix(), "master_frame": frame, "pose": pose,
                                   "beam_intensity": inten, "t": round(now, 3)})
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

def read_preflight(adapter, p, regex):
    """Every read the plans make, once, BEFORE any change: a bad binding refuses at arm."""
    w, h = p["resolution"]
    pose = adapter.camera_pose(float(w) / float(h), p["fov_fallback_deg"])
    if pose is None:
        raise BenchRefused("no_camera", "no player camera manager in PIE")
    beams = adapter.beam_rows(regex)
    if len(beams) != 1:
        raise BenchRefused("beam_not_found", "%d lights match %s" % (len(beams), regex))
    beam = beams[0]
    fogs = adapter.fogs()
    if not any(f["volumetric_fog"] for f in fogs):
        raise BenchRefused("no_volumetric_fog", "no ExponentialHeightFog with volumetric fog on: no beam to texture")
    cvars = {n: adapter.cvar(n) for n in sorted(p["d_cvars"])}
    vf = adapter.cvar("r.VolumetricFog")
    if vf is not None and float(vf) < 0.5:
        raise BenchRefused("no_volumetric_fog", "r.VolumetricFog=%s" % vf)
    probe = adapter.trace(tuple(pose["loc"]), (pose["loc"][0], pose["loc"][1], pose["loc"][2] - 10.0),
                          beam["actor_id"])
    meshes = adapter.meshes_near(beam["location"], 100.0, 4, float(p["a_wing_max_extent_cm"]))
    return {"beam": beam, "fogs": len(fogs), "cvars": cvars, "r.VolumetricFog": vf, "trace_ok": True,
            "trace_probe_hit": probe is not None, "meshes_probe": len(meshes), "exposure": adapter.exposure_info()}


def arm(adapter, prepare_path=None, params=None, dry=False, out_root=OUT_ROOT, prepare_root=PREPARE_ROOT,
        owner_path=OWNER, log_path=LOG_PATH, register=None, unregister=None, store=builtins, luma_reader=None,
        clock=time.monotonic):
    p = dict(DEFAULTS)
    p.update(params or {})
    run_id = "BEAMTEX-%s%s" % (utc_stamp(), "-dry" if dry else "")
    adapter.log("%s_START|run=%s|dry=%s|variants=%s" % (MARK, run_id, bool(dry), ",".join(p["variants"])))

    def refuse(exc):
        tagged = BenchRefused(exc.reason, exc.detail, run_id)
        adapter.log_error(str(tagged))
        raise tagged from exc

    try:
        bad = [v for v in p["variants"] if v not in ORDER]
        if bad or list(p["variants"])[:1] != ["base"] or len(set(p["variants"])) != len(p["variants"]):
            raise BenchRefused("bad_variants", "base must come first, no repeats; known %s" % ",".join(ORDER))
        names = [str(x["name"]) for x in p["positions"]]
        if not names or len(set(names)) != len(names):
            raise BenchRefused("bad_positions", ",".join(names))
        if adapter.world_kind() != "game":
            raise BenchRefused("no_pie", "start PIE first (conductor_pie_begin.py); PREPARE comes before PIE")
        missing_api = adapter.api_missing()
        if missing_api:
            raise BenchRefused("api_missing", ",".join(missing_api))
        handles = ps.armed_handles(store)
        if handles:
            raise BenchRefused("tick_armed", ",".join(handles))
        if ps.owner_active(owner_path):
            raise BenchRefused("pie_owner_active", pathlib.Path(owner_path).as_posix())
        prep_path = find_prepare_record(prepare_root, prepare_path)
        prep = load_prepare_record(prep_path)
        newest = sorted(pathlib.Path(prepare_root).glob("*/" + PREPARE_RECORD_NAME))
        if newest and newest[-1].resolve() != pathlib.Path(prep_path).resolve():
            raise BenchRefused("stale_prepare", "%s is not the newest PREPARE %s" % (
                pathlib.Path(prep_path).as_posix(), newest[-1].as_posix()))
        if not lb.same_level(prep.get("world"), adapter.world_name()):
            raise BenchRefused("wrong_world", "prepared %s, PIE %s" % (prep.get("world"), adapter.world_name()))
        pool = adapter.pool_labels()
        missing = [l for l in pool_labels_needed(p) if l not in pool]
        if missing:
            raise BenchRefused("pool_missing", "%d %s; run PREPARE before PIE" % (len(missing), ",".join(missing)))
        lit = [l for l in pool if adapter.pool_state(l)["on"]]
        if lit:
            raise BenchRefused("pool_not_base", "%s; run RESTORE first" % ",".join(lit))
        log_text = pathlib.Path(log_path).read_text(encoding="utf-8", errors="replace") \
            if pathlib.Path(log_path).is_file() else ""
        errs = compile_errors_since(log_text, prep.get("marker") or "\x00", BENCH_MATERIALS)
        needed = set()
        if any(v in ("B", "ALL") for v in p["variants"]):
            needed.add(MAT_NOISE)
        if any(v in ("A", "ALL") for v in p["variants"]) and p["a_occluder_policy"] != "never":
            needed.add(MAT_BREAKUP if p["a_occluder"] == "breakup" else MAT_BLACK)
        if errs is None and needed:
            raise BenchRefused("compile_unknown", "PREPARE marker %r not in %s: cannot judge the bench materials" % (
                prep.get("marker"), pathlib.Path(log_path).as_posix()))
        bad_mats = sorted(m for m in needed if any(m.rsplit("/", 1)[-1] in ln for ln in (errs or [])))
        if bad_mats:
            raise BenchRefused("material_compile_failed", ",".join(bad_mats))
        n, seg_label = ps.passage_label(p["passage"])
        segment = adapter.passage_segment(seg_label)
        census_before = adapter.census()
        regex = beam_regex(p)
        preflight = read_preflight(adapter, p, regex)
    except BenchRefused as exc:
        refuse(exc)
    except Exception as exc:
        refuse(BenchRefused("arm_error", "%s: %s" % (type(exc).__name__, exc)))
    adapter.log("%s_PREFLIGHT|run=%s|%s" % (MARK, run_id, json.dumps(plain(preflight), sort_keys=True, default=str)[:900]))
    original_frame = int(adapter.transport_frame())
    run_dir = pathlib.Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    bench = BeamBench(adapter, run_dir / ORIGINALS_NAME, p, run_id)
    bench.read_globals(census_before, prep)
    positions = [{"i": i, "name": str(x["name"]), "ahead_cm": float(x["ahead_cm"])} for i, x in enumerate(p["positions"])]
    adapter.log("%s_ANNOUNCE|run=%s|world=PIE|%s bay %d %s|changes the beam's shadow flags, height fog density / "
                "scattering distribution and %d volumetric-fog cvars in PIE only, shows prepared %s* actors (no "
                "spawns); every change recorded and restored at the end; the map and %s are dirty from PREPARE: "
                "Don't-Save restart after|record=%s" % (
                    MARK, run_id, p["passage"], int(p["bay"]), preflight["beam"]["label"], len(p["d_cvars"]), PREFIX,
                    ASSET_DIR, bench.record_path.as_posix()))
    try:
        bench.neutralise()
    except Exception:
        problems = bench.restore()
        adapter.log_error("%s_FAILED|run=%s|reason=neutralise|restored problems=%r" % (MARK, run_id, problems))
        raise
    run = {"run_id": run_id, "run_dir": run_dir.as_posix(), "dry": bool(dry), "params": plain(p),
           "positions": positions, "census_before": census_before, "original_frame": original_frame,
           "world": adapter.world_name(), "prepare_record": pathlib.Path(prep_path).as_posix(),
           "prepare_materials": prep.get("materials"), "substrate": prep.get("substrate"),
           "segment": list(segment), "beam_regex": regex, "beam": preflight["beam"], "preflight": preflight,
           "exposure": preflight["exposure"], "started_utc": utc_iso(), "status": "armed", "errors": [],
           "route": "passage_stills: Master scrub (ScrubToMasterFrame) + live camera pose; no actor moved"}
    manifest = run_dir / MANIFEST_NAME
    write_verified(manifest, run)
    machine = BeamMachine(bench, adapter, run, luma_reader=luma_reader)
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
        shots = 0
        for pos in positions:
            for _v, shot in (pos.get("shots") or {}).items():
                for s in shot["stills"]:
                    shots += 1
                    path = pathlib.Path(s["path"])
                    s["exists"] = path.is_file()
                    if not s["exists"] or path.stat().st_size <= int(p["file_min_bytes"]):
                        problems.append("missing or undersized still: " + s["path"])
            pos.pop("_plans", None)
        want = len(positions) * (1 if dry else len(p["variants"])) * int(p["stills_per_shot"])
        if status_hint == "complete" and shots != want:
            problems.append("stills %d != expected %d" % (shots, want))
        gates = list(machine.st["gate_failures"])
        run.update(gate_failures=gates, problems=problems, finished_utc=utc_iso(),
                   task_log=machine.st["task_log"], probe_timeouts=machine.st["probe_timeouts"],
                   wall_seconds=round(clock() - run["_t_start"], 1))
        ok = status_hint == "complete" and machine.done and not problems and not gates and not run["errors"]
        run["status"] = "passed" if ok else "failed"
        bench.record["status"] = "restored" if not [x for x in problems if "!=" in x or "still shown" in x] \
            else "dirty"
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
            adapter.log("%s_CAPTURE_OK|run=%s|positions=%d|variants=%d|stills=%d|seconds=%.0f|dir=%s" % (
                MARK, run_id, len(positions), 1 if dry else len(p["variants"]), shots, run["wall_seconds"],
                run_dir.as_posix()))
        else:
            reasons = [r.split(" ")[0].split(":")[0] for r in (problems + gates)] or [status_hint]
            if run["errors"]:
                reasons.insert(0, run.get("error_reason", "error"))
            adapter.log_error("%s_FAILED|run=%s|reason=%s|problems=%r|gate_failures=%r|manifest=%s" % (
                MARK, run_id, ";".join(reasons), problems[:8], gates[:12], manifest.as_posix()))
        adapter.log("%s|run=%s|the %s pool, the dirty map and the unsaved %s materials remain: end PIE, then restart "
                    "the editor choosing Don't Save" % (RESTART, run_id, PREFIX, ASSET_DIR))
        run["finished"] = True

    def tick(delta=0.0):
        if run.get("inside") or run.get("finished"):
            return
        run["inside"] = True
        try:
            now = clock()
            if now - run["_t_start"] > float(p["run_timeout_s"]):
                raise BenchRefused("run_timeout", "%.0f s" % float(p["run_timeout_s"]), run_id)
            machine.step(now, float(delta or 0.0))
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
        "%s@%.0fcm" % (r["name"], r["ahead_cm"]) for r in positions), run_dir.as_posix()))
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

    def main_comp(actor):
        if isinstance(actor, unreal.LocalFogVolume):
            return "fog", actor.get_component_by_class(unreal.LocalFogVolumeComponent)
        return "mesh", actor.static_mesh_component

    def pool_state(label):
        kind, comp = main_comp(pool_actor(label))
        on = bool(comp.is_visible())
        if kind == "fog":
            on = on or float(comp.get_editor_property("height_fog_extinction")) > 0.0 \
                or float(comp.get_editor_property("radial_fog_extinction")) > 0.0
        return {"on": on, "kind": kind}

    def census():
        lib = unreal.EditorLoadingAndSavingUtils
        return {"maps": ps.package_names(lib.get_dirty_map_packages()),
                "content": ps.package_names(lib.get_dirty_content_packages())}

    return all_actors, pool_map, pool_actor, main_comp, pool_state, census


def _sampler_for(compression, srgb):
    """s3_marble_tiling_material.py:143-155 (grayscale non-sRGB needs LINEAR_GRAYSCALE: memory)."""
    c = str(compression).upper()
    if "NORMALMAP" in c:
        return "SAMPLERTYPE_NORMAL"
    if "MASKS" in c:
        return "SAMPLERTYPE_MASKS"
    if "GRAYSCALE" in c:
        return "SAMPLERTYPE_GRAYSCALE" if srgb else "SAMPLERTYPE_LINEAR_GRAYSCALE"
    return "SAMPLERTYPE_COLOR" if srgb else "SAMPLERTYPE_LINEAR_COLOR"


def make_editor_adapter(unreal):
    """PREPARE: the EDITOR world, only while no PIE world exists. Creates the bench materials CREATE-ONLY (never a
    node deleted, never an existing asset touched) and spawns the hidden pool."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = editor_sub.get_editor_world()
    handles = {}
    events = []
    all_actors, pool_map, pool_actor, main_comp, pool_state, census = _pool_common(unreal, world, handles)

    def create_material(path):
        eal = unreal.EditorAssetLibrary
        if eal.does_asset_exist(path):
            raise RuntimeError("%s_ASSET_EXISTS|%s" % (MARK, path))
        d, name = path.rsplit("/", 1)
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, d, unreal.Material,
                                                                      unreal.MaterialFactoryNew())
        if mat is None:
            raise RuntimeError("%s_ASSET_CREATE_FAILED|%s" % (MARK, path))
        events.append(("create_asset", path))
        return mat

    def node(mat, cls, x, y, **props):
        n = unreal.MaterialEditingLibrary.create_material_expression(mat, cls, x, y)
        if n is None:
            raise RuntimeError("%s_CREATE_NODE|%s" % (MARK, cls))
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def link(a, a_out, b, b_in):
        mel = unreal.MaterialEditingLibrary
        ok = mel.connect_material_expressions(a, a_out, b, b_in)
        if not ok and len(mel.get_material_expression_input_names(b)) == 1:
            ok = mel.connect_material_expressions(a, a_out, b, "")
        if not ok:
            raise RuntimeError("%s_LINK|%s.%s->%s.%s" % (MARK, a.get_name(), a_out, b.get_name(), b_in))

    def custom(mat, x, y, desc, code, inputs):
        n = node(mat, unreal.MaterialExpressionCustom, x, y, description=desc, code=code,
                 output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        ins = []
        for name in inputs:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", name)
            ins.append(ci)
        n.set_editor_property("inputs", ins)
        return n

    def scalar(mat, name, value, x, y):
        return node(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name,
                    default_value=float(value), group="BeamTex")

    def prop(src, out, mp):
        if not unreal.MaterialEditingLibrary.connect_material_property(src, out, mp):
            raise RuntimeError("%s_PROP|%s" % (MARK, mp))

    def readback(mat, want):
        """Judge by read-back, never by setter return values (memory: the setter lies)."""
        rb = {"domain": str(mat.get_editor_property("material_domain")),
              "blend_mode": str(mat.get_editor_property("blend_mode")),
              "shading_model": str(mat.get_editor_property("shading_model")),
              "expressions": len(unreal.MaterialEditingLibrary.get_material_expressions(mat))}
        rb["ok"] = all(tok in rb[k] for k, tok in want.items()) and rb["expressions"] > 0
        rb["want"] = want
        return rb

    def build_black(p):
        mat = create_material(MAT_BLACK)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        black = node(mat, unreal.MaterialExpressionConstant3Vector, -400, 0,
                     constant=unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        prop(black, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        return readback(mat, {"blend_mode": "OPAQUE", "shading_model": "UNLIT", "domain": "SURFACE"})

    def build_breakup(p):
        tex = unreal.load_asset(p["a_breakup_texture"].split(".")[0])
        if tex is None:
            raise RuntimeError("%s_TEXTURE_MISSING|%s" % (MARK, p["a_breakup_texture"]))
        st_name = _sampler_for(tex.get_editor_property("compression_settings"), bool(tex.get_editor_property("srgb")))
        mat = create_material(MAT_BREAKUP)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        mat.set_editor_property("two_sided", True)
        uv = node(mat, unreal.MaterialExpressionTextureCoordinate, -900, 0,
                  u_tiling=float(p["a_breakup_tiling"]), v_tiling=float(p["a_breakup_tiling"]))
        smp = node(mat, unreal.MaterialExpressionTextureSample, -650, 0, texture=tex,
                   sampler_type=getattr(unreal.MaterialSamplerType, st_name))
        link(uv, "", smp, "UVs")
        thr = scalar(mat, "Threshold", p["a_breakup_threshold"], -650, 250)
        con = scalar(mat, "Contrast", p["a_breakup_contrast"], -650, 350)
        cut = custom(mat, -350, 100, "BeamTex breakup threshold", CODE_BREAKUP, ["X", "Thr", "Contrast"])
        link(smp, "R", cut, "X")
        link(thr, "", cut, "Thr")
        link(con, "", cut, "Contrast")
        prop(cut, "", unreal.MaterialProperty.MP_OPACITY_MASK)
        black = node(mat, unreal.MaterialExpressionConstant3Vector, -350, -150,
                     constant=unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        prop(black, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        out = readback(mat, {"blend_mode": "MASKED", "shading_model": "UNLIT"})
        out["sampler"] = st_name
        return out

    def build_noise(p):
        mat = create_material(MAT_NOISE)
        # blend BEFORE domain: Volume + the default Opaque blend logs "Failed to compile" for that transient state
        # (measured 6 Oct, beamtex_b_probe2.py: final shader identical either way), which the compile gate caught
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
        mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
        # not UNLIT: the non-Substrate voxeliser reads Extinction from SubsurfaceColor.r only when the shading model
        # is not unlit (VolumetricFogVoxelization.usf:36-38)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        wp = node(mat, unreal.MaterialExpressionWorldPosition, -1200, 0,
                  world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
        wpf = node(mat, unreal.MaterialExpressionTruncateLWC, -1000, 0)       # s3_marble_tiling_material.py:537-540
        link(wp, "", wpf, "")
        tm = node(mat, unreal.MaterialExpressionTime, -1000, 120)
        cus = custom(mat, -600, 100, "BeamTex 3D value noise extinction (1/m)", CODE_NOISE3, NOISE_INPUTS)
        link(wpf, "", cus, "WP")
        link(tm, "", cus, "T")
        for k, (pin, pkey) in enumerate(sorted(NOISE_PARAMS.items())):
            link(scalar(mat, pin, p[pkey], -1000, 250 + 100 * k), "", cus, pin)
        alb = node(mat, unreal.MaterialExpressionConstant3Vector, -600, -150,
                   constant=unreal.LinearColor(float(p["b_albedo"]), float(p["b_albedo"]), float(p["b_albedo"]), 1.0))
        prop(alb, "", unreal.MaterialProperty.MP_BASE_COLOR)              # Albedo (VolumetricFogVoxelization.usf:55-66)
        prop(cus, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)        # Extinction (:29-41)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        return readback(mat, {"domain": "VOLUME", "blend_mode": "ADDITIVE"})

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

        def api_missing(self):
            return api_missing(unreal, EDITOR_API)

        def cvar_int(self, name):
            try:
                return int(unreal.SystemLibrary.get_console_variable_int_value(name))
            except Exception:
                return None

        def asset_exists(self, path):
            return bool(unreal.EditorAssetLibrary.does_asset_exist(path))

        def build_materials(self, p):
            out = {}
            for path, fn in ((MAT_BLACK, build_black), (MAT_BREAKUP, build_breakup), (MAT_NOISE, build_noise)):
                out[path] = fn(p)
                unreal.log("%s_MATERIAL|%s|%s" % (MARK, path, json.dumps(out[path], sort_keys=True)))
            return out

        def bench_actor_labels(self, prefix):
            return sorted(a.get_actor_label() for a in all_actors() if a.get_actor_label().startswith(prefix))

        def pool_labels(self):
            return sorted(pool_map())

        def pool_state(self, label):
            return pool_state(label)

        def spawn_hidden(self, spec):
            """look_bench.py:1331-1366: editor world only, hidden, Movable, collision off, tagged."""
            events.append(("spawn", spec["label"]))
            cls = unreal.LocalFogVolume if spec["kind"] == "fog" else unreal.StaticMeshActor
            actor = actor_sub.spawn_actor_from_class(cls, unreal.Vector(0.0, 0.0, -100000.0),
                                                     unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            if actor is None:
                raise RuntimeError("%s_SPAWN_FAILED|%s" % (MARK, spec["label"]))
            if actor.get_world() != world:
                actor_sub.destroy_actor(actor)
                raise RuntimeError("%s_SPAWN_NOT_IN_EDITOR_WORLD|%s" % (MARK, spec["label"]))
            actor.set_actor_label(spec["label"], False)
            actor.set_editor_property("tags", [unreal.Name(TAG)])
            actor.set_actor_enable_collision(False)
            kind, comp = main_comp(actor)
            if kind == "fog":
                comp.set_radial_fog_extinction(0.0)
                comp.set_height_fog_extinction(0.0)
            else:
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_static_mesh(unreal.load_object(None, spec["mesh"]))
                comp.set_material(0, unreal.load_asset(spec["material"]))
                comp.set_cast_shadow(bool(spec["cast_shadow"]))                # PrimitiveComponent.h:1965
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
    """CAPTURE / RESTORE: the PIE game world. Reads and sets with runtime (UFUNCTION) setters; places, shows and
    hides the prepared pool; console variables through ExecuteConsoleCommand."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    first = editor_sub.get_game_world()
    first_name = first.get_path_name() if first is not None else None
    handles = {}
    events = []
    _all, pool_map, pool_actor, main_comp, pool_state, census = _pool_common(unreal, first, handles)
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

    def rot_dict(r):
        return {"roll": float(r.roll), "pitch": float(r.pitch), "yaw": float(r.yaw)}

    def vec(v):
        return [float(v.x), float(v.y), float(v.z)]

    def fog_read(comp, field):
        if field == "fog_density":
            return float(comp.get_editor_property("fog_density"))
        if field == "second_fog_density":
            return float(comp.get_editor_property("second_fog_data").get_editor_property("fog_density"))
        if field == "scattering_distribution":
            return float(comp.get_editor_property("volumetric_fog_scattering_distribution"))
        if field == "volumetric_fog":
            for name in ("enable_volumetric_fog", "volumetric_fog"):
                try:
                    return bool(comp.get_editor_property(name))
                except Exception:
                    continue
            raise RuntimeError("%s_FOG_FIELD|volumetric_fog" % MARK)
        raise RuntimeError("%s_FOG_FIELD|%s" % (MARK, field))

    def first_hit(result):
        """capture_settle_options.py:108-128: (bool, HitResult) or HitResult; None = no hit. to_tuple() measured as
        [blocking, start_penetrating, time, distance, location, impact_point, normal, impact_normal, phys_mat,
        hit_actor, hit_component, ...] (BreakHitResult order)."""
        hit = result[1] if isinstance(result, tuple) else result
        if hit is None:
            return None
        fields = hit.to_tuple()
        if not fields[0]:
            return None
        label, comp = "?", ""
        comps = [f for f in fields if isinstance(f, unreal.ActorComponent) and f.get_owner()]
        acts = [f for f in fields if isinstance(f, unreal.Actor)]
        if comps:                                  # the component names the wing panel; the actor alone may be
            label, comp = comps[0].get_owner().get_actor_label(), comps[0].get_name()   # a whole Passage
        elif acts:
            label = acts[0].get_actor_label()
        return {"dist": float(fields[3]), "label": label, "component": comp}

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

        def api_missing(self):
            return api_missing(unreal, PIE_API)

        def console(self, command):
            world = live_world()
            if world is None:
                raise BenchRefused("pie_ended", "console with no PIE world")
            unreal.SystemLibrary.execute_console_command(world, command)

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

        # ---- reads
        def beam_rows(self, regex):
            rx = re.compile(regex)
            skip = tuple(getattr(unreal, n) for n in SKIP_LIGHT_CLASSES if hasattr(unreal, n))
            rows = []
            for actor in actors_of(unreal.Actor):
                label = actor.get_actor_label()
                if not rx.search(label) or (skip and isinstance(actor, skip)):
                    continue
                comps = list(actor.get_components_by_class(unreal.LocalLightComponent))
                if len(comps) != 1:
                    continue
                comp = comps[0]
                cid = comp.get_path_name()
                handles[cid] = comp
                handles[actor.get_path_name()] = actor
                is_spot = isinstance(comp, unreal.SpotLightComponent)
                rows.append({"id": cid, "actor_id": actor.get_path_name(), "label": label,
                             "location": vec(comp.get_world_location()),
                             "rotation": rot_dict(comp.get_world_rotation()),
                             "outer_cone_deg": float(comp.get_editor_property("outer_cone_angle")) if is_spot else 80.0,
                             "attenuation_cm": float(comp.get_editor_property("attenuation_radius")),
                             "intensity": float(comp.get_editor_property("intensity")),
                             "cast_shadows": bool(comp.get_editor_property("cast_shadows")),
                             "cast_volumetric_shadow": bool(comp.get_editor_property("cast_volumetric_shadow")),
                             "volumetric_scattering_intensity": float(
                                 comp.get_editor_property("volumetric_scattering_intensity")),
                             "spot": is_spot, "visible": bool(comp.is_visible())})
            return sorted(rows, key=lambda r: r["id"])

        def fogs(self):
            rows = []
            for actor in actors_of(unreal.ExponentialHeightFog):
                comp = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
                cid = comp.get_path_name()
                handles[cid] = comp
                rows.append({"id": cid, "label": actor.get_actor_label(),
                             "fog_density": fog_read(comp, "fog_density"),
                             "second_fog_density": fog_read(comp, "second_fog_density"),
                             "volumetric_fog": fog_read(comp, "volumetric_fog"),
                             "scattering_distribution": fog_read(comp, "scattering_distribution")})
            return rows

        def cvar(self, name):
            try:
                return float(unreal.SystemLibrary.get_console_variable_float_value(name))   # KismetSystemLibrary.h:622
            except Exception:
                return None

        def trace(self, start, end, ignore_actor_id=None):
            world = live_world()
            ignore = [get(ignore_actor_id)] if ignore_actor_id else []
            ignore += [a for a in pool_map().values()]
            res = unreal.SystemLibrary.line_trace_single(          # KismetSystemLibrary.h:1270
                world, unreal.Vector(*start), unreal.Vector(*end), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True,
                ignore, unreal.DrawDebugTrace.NONE, True)
            return first_hit(res)

        def meshes_near(self, center, radius, max_rows, max_extent):
            rows = []
            for actor in actors_of(unreal.Actor):
                label = actor.get_actor_label()
                if label.startswith(PREFIX):
                    continue
                for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                    if not comp.is_visible():
                        continue
                    origin, extent, _r = unreal.SystemLibrary.get_component_bounds(comp)
                    ext = [float(extent.x), float(extent.y), float(extent.z)]
                    if max(ext) > max_extent:            # an ISM's bounds cover all its instances: useless here
                        continue
                    c = [float(origin.x), float(origin.y), float(origin.z)]
                    if math.dist(c, center) - math.sqrt(sum(e * e for e in ext)) > radius:
                        continue
                    rows.append({"label": label, "component": comp.get_name(), "center": c, "extent": ext})
            rows.sort(key=lambda r: math.dist(r["center"], center))
            return rows[:int(max_rows)]

        def exposure_info(self):
            """Read-only record of the unbound PPVs' exposure (memory: the show runs min = max = -3)."""
            out = []
            for v in actors_of(unreal.PostProcessVolume):
                if not bool(v.get_editor_property("unbound")) or not bool(v.get_editor_property("enabled")):
                    continue
                s = v.get_editor_property("settings")
                row = {"label": v.get_actor_label()}
                for f in fb.PP_EXPOSURE + fb.PP_READ_ONLY:
                    try:
                        row[f] = fb.plain_pp(s.get_editor_property(f))
                    except Exception:
                        row[f] = None
                out.append(row)
            return out

        # ---- generic property access by (kind, id, field)
        def read(self, kind, oid, field):
            if kind == "light":
                comp = get(oid)
                if field in ("cast_shadows", "cast_volumetric_shadow"):
                    return bool(comp.get_editor_property(field))
                raise RuntimeError("%s_LIGHT_FIELD|%s" % (MARK, field))
            if kind == "fog":
                return fog_read(get(oid), field)
            if kind == "cvar":
                return float(unreal.SystemLibrary.get_console_variable_float_value(oid))
            raise RuntimeError("%s_BAD_KIND|%s" % (MARK, kind))

        def write(self, kind, oid, field, value):
            events.append(("write", kind, oid, field))
            if kind == "light":
                comp = get(oid)
                if field == "cast_shadows":
                    comp.set_cast_shadows(bool(value))                 # LightComponentBase.h:146
                elif field == "cast_volumetric_shadow":
                    comp.set_cast_volumetric_shadow(bool(value))       # LightComponentBase.h:153
                else:
                    raise RuntimeError("%s_LIGHT_FIELD|%s" % (MARK, field))
            elif kind == "fog":
                comp = get(oid)
                if field == "fog_density":
                    comp.set_fog_density(float(value))
                elif field == "second_fog_density":
                    comp.set_second_fog_density(float(value))
                elif field == "scattering_distribution":
                    comp.set_volumetric_fog_scattering_distribution(float(value))   # ...FogComponent.h:308
                else:
                    raise RuntimeError("%s_FOG_FIELD|%s" % (MARK, field))
            elif kind == "cvar":
                v = float(value)
                text = str(int(v)) if v.is_integer() else repr(v)
                unreal.SystemLibrary.execute_console_command(live_world(), "%s %s" % (oid, text))
            else:
                raise RuntimeError("%s_BAD_KIND|%s" % (MARK, kind))

        # ---- show strobes and sweep lights (p02_fog_bench.py:1981-2007)
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
            return pool_state(label)

        def show_pool(self, spec):
            events.append(("show", spec["label"]))
            actor = pool_actor(spec["label"])
            kind, comp = main_comp(actor)
            r = spec.get("rot") or {"roll": 0.0, "pitch": 0.0, "yaw": float(spec.get("yaw", 0.0))}
            actor.set_actor_location_and_rotation(unreal.Vector(*spec["loc"]),
                                                  unreal.Rotator(roll=float(r["roll"]), pitch=float(r["pitch"]),
                                                                 yaw=float(r["yaw"])), False, True)
            got = actor.get_actor_location()
            if math.dist((got.x, got.y, got.z), tuple(spec["loc"])) > 1.0:
                raise RuntimeError("%s_MOVE_FAILED|%s (not Movable?)" % (MARK, spec["label"]))
            if kind == "fog":
                s = float(spec["scale"])
                actor.set_actor_scale3d(unreal.Vector(s, s, s))
                comp.set_radial_fog_extinction(float(spec["radial"]))
                comp.set_height_fog_extinction(float(spec["height"]))
                comp.set_height_fog_falloff(float(spec["falloff"]))
                comp.set_height_fog_offset(float(spec["offset"]))
                comp.set_fog_phase_g(float(spec["phase_g"]))
            else:
                actor.set_actor_scale3d(unreal.Vector(*spec["scale"]))
            comp.set_visibility(True, True)
            actor.set_actor_hidden_in_game(False)

        def hide_pool(self, label):
            events.append(("hide", label))
            actor = pool_actor(label)
            kind, comp = main_comp(actor)
            if kind == "fog":
                comp.set_radial_fog_extinction(0.0)
                comp.set_height_fog_extinction(0.0)
            comp.set_visibility(False, True)
            actor.set_actor_hidden_in_game(True)

    adapter = PieAdapter()
    adapter.events = events
    return adapter
# ---- PIE ADAPTER END ----


def main():
    import unreal
    g = globals()
    mode = g.get("BENCH_MODE", "")
    params = dict(g.get("BENCH_PARAMS", {}) or {})
    if mode == "PREPARE":
        adapter = make_editor_adapter(unreal)
        run_id = "BEAMTEXPREP-" + utc_stamp()
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
        run_id = "BEAMTEXRESTORE-" + utc_stamp()
        if adapter.world_kind() != "game":
            unreal.log_error("%s_FAILED|run=%s|reason=no_pie|RESTORE works on the PIE copies" % (MARK, run_id))
            raise RuntimeError("no PIE")
        if HANDLE_NAME in ps.armed_handles(builtins):
            unreal.log_error("%s_FAILED|run=%s|reason=tick_armed|a capture is still running; it restores itself"
                             % (MARK, run_id))
            raise RuntimeError("armed")
        explicit = g.get("BENCH_RECORD")
        records = ([explicit] if isinstance(explicit, (str, pathlib.Path)) else list(explicit)) if explicit else \
            session_records()
        unreal.log("%s_RESTORE_RECORDS|run=%s|%s" % (MARK, run_id, ",".join(pathlib.Path(r).as_posix()
                                                                           for r in records) or "none"))
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
