"""P06 SUNSET (Gary 7 Oct): a low sun is already up as Passage 6 begins, sets over ~40 s with the light raking across the
route ahead of Puss, then TOTAL darkness (artificial lights only) for the rest of P06. "A last drip of sublimity."
Offline-written 7 Oct, NEVER RUN IN UNREAL. Harness: test_p06_sunset_offline.py (system Python, no Unreal). Plan and
evidence: P06_SUNSET_PLAN.md (same folder).

Tiers per claim: [decl] declaration/source-proven (file:line we can read), [meas] an earlier run's read-back record
(cited), [prec] in-repo precedent call (cited), [inf] inferred (why).

MECHANISM
  * Temporality lives on FInfinityPassageSettings::CelestialCycle, NOT on a cue [decl InfinityStageTypes.h:947 struct
    start, :1020-1022 field]. Matched to the compiled Passage by PassageGuid [decl InfinityStageCompiler.cpp:437-445].
  * phase(P, t) = InitialPhaseCycles + sum over Passages up to and incl. P of EntryPhaseOffsetCycles + full elapsed of
    every EARLIER Passage * Rate/Duration + elapsed-in-P * Rate/Duration, elapsed clamped to [0, segment] and measured
    from the compiled SegmentStartFrame (includes lead-in) [decl Compiler.cpp:413-470, :254]. Rate = 0 when !bAnimate.
  * sin(elevation) = -cos(2*pi*phase); sun pitch = 90 - 360*phase, yaw = SunAzimuthDegrees; daylight =
    SmoothStep(-Band, Band, sin(elev)); sun lux = MaximumSunIntensity * daylight; moon lux = MaximumMoonIntensity *
    SmoothStep(-Band, Band, -sin(elev)); sky light = lerp(Night, Day, daylight) [decl InfinityStageCelestialRig.cpp:
    449-513]. On the setting branch (phase 0.5..1) elevation = 270 - 360*phase, linear [inf: algebra, tested].
  * The pin: bApplyManualLightingInGame makes PIE use EditorPreviewTimeHours and IGNORE the Master phase [decl
    CelestialRig.cpp:184-197, 219-229]. It is ON in production (set by Saved/CodexLighting/reopen_step1.py:8 [prec];
    CELESTIAL_MANUAL_LIGHTING_IN_GAME|hours=0.00 logged in PIE as late as 2026.10.07-03.32 [meas Saved/Logs]). And
    MaximumSunIntensity = 0 [meas black_void_record.json 5 Oct]. So a Show write ALONE IS INERT: this tool also writes
    the rig (level): pin off, sun lux, azimuth, twilight band.
  * Why the rig writes are effectively P06-only: every other Passage is bAnimate=false with offset 0 and
    InitialPhaseCycles = 0 [meas CodexLighting/apply_night_stage1_result.json, 18 Sep; RE-READ by DRY], so they sit at
    phase 0 = the pinned hour 0 exactly -> daylight 0 -> sun 0 lux whatever MaximumSunIntensity is. P06 is the LAST
    Passage [meas probe_routes.json, 6 rows], so its advance reaches no later Passage. DRY refuses if either changed.
  * No Master rebuild, no materialise: the phase is compiled from the live Show at evaluate time [decl Compiler.cpp:
    425-429] and no Passage actor reads CelestialCycle [decl: grep CelestialCycle hits only Compiler.cpp + Types.h].

Modes (p06_sunset_run.py <- p06_sunset_args.json, confirm "<MODE> P06SUNSET"):
  DRY    read-only -> p06_sunset_dry.json; P06_SUNSET_DRY_OK|run=..|apply_ready=..
  APPLY  guards -> plan refusals -> backup Show + umap -> exclusive fsynced record -> Show write (read back) -> rig
         write (read back) -> optional in-editor probe (manual off, EvaluateAtMasterFrame at sample frames, restore) ->
         census == {Show, level} -> save those two -> read back -> census clean -> P06_SUNSET_APPLY_OK|run=..
  REVERT drift check -> backup -> restore recorded Show cycle + rig props -> save -> read back -> P06_SUNSET_REVERT_OK
  Failure: P06_SUNSET_STOPPED|run=..|reason=..
Never: Save All, reload the level, open/scrub Sequencer, end PIE; no unreal objects in module globals.
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


MARK = "P06_SUNSET"
CONFIRM_SUFFIX = "P06SUNSET"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"            # p06_tail_extend.py:83
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"   # black_void.py:17
ARGS_NAME = "p06_sunset_args.json"
DRY_NAME = "p06_sunset_dry.json"
RECORD_NAME = "p06_sunset_record.json"
RIG_KEYS = ("apply_manual_lighting_in_game", "maximum_sun_intensity", "sun_azimuth_degrees", "twilight_altitude_band")
DARK_KEYS = ("maximum_moon_intensity", "day_sky_light_intensity", "night_sky_light_intensity")
CYCLE_KEYS = ("animate", "cycle_duration_seconds", "cycle_rate_multiplier", "entry_phase_offset_cycles")
EPS = 1e-9


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure maths: a mirror of InfinityStageCelestialRig.cpp:449-470 and InfinityStageCompiler.cpp:432-470
# =====================================================================================================================

def frac(x):
    return x - math.floor(x)


def smoothstep(a, b, x):
    """FMath::SmoothStep: 0 below A, 1 at/above B, Hermite between [inf: UE Core header semantics]."""
    if x < a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def solar_altitude(phase):
    """sin(elevation) = -cos(2 pi phase) [decl CelestialRig.cpp:451-452]."""
    return -math.cos(frac(phase) * 2.0 * math.pi)


def elevation_deg(phase):
    return math.degrees(math.asin(max(-1.0, min(1.0, solar_altitude(phase)))))


def daylight(phase, band):
    b = max(band, 0.001)
    return smoothstep(-b, b, solar_altitude(phase))


def moonlight(phase, band):
    b = max(band, 0.001)
    return smoothstep(-b, b, -solar_altitude(phase))


def sun_rotator(phase, azimuth):
    """FRotator(pitch, yaw, 0) written to the sun actor [decl CelestialRig.cpp:460, 490]."""
    return 90.0 - frac(phase) * 360.0, azimuth


def forward_vector(pitch, yaw):
    """UE rotator -> X axis: (cos p cos y, cos p sin y, sin p); X forward, Y right, Z up [inf: UE convention]."""
    p, y = math.radians(pitch), math.radians(yaw)
    return (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))


def sun_position(phase, azimuth):
    """Where the sun IS seen from = minus the light's travel direction (a directional light shines along its forward
    axis [inf: UE convention; APPLY probe re-derives it from the live actor]). Returns (elevation_deg, azimuth_deg)."""
    f = forward_vector(*sun_rotator(phase, azimuth))
    s = (-f[0], -f[1], -f[2])
    return math.degrees(math.asin(max(-1.0, min(1.0, s[2])))), math.degrees(math.atan2(s[1], s[0])) % 360.0


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def integrated_phase(passages, target_index, elapsed_s, initial_phase):
    """Mirror of Compiler.cpp:432-470. passages: ordered dicts {animate, cycle_duration_seconds, cycle_rate_multiplier,
    entry_phase_offset_cycles, seconds}. elapsed clamped to [0, seconds]."""
    phase = initial_phase
    for i, p in enumerate(passages):
        dur = max(float(p["cycle_duration_seconds"]), 1e-4)
        rate = max(0.0, float(p["cycle_rate_multiplier"])) if p["animate"] else 0.0
        phase += float(p["entry_phase_offset_cycles"])
        if i == target_index:
            return frac(phase + min(max(elapsed_s, 0.0), float(p["seconds"])) * rate / dur)
        phase += float(p["seconds"]) * rate / dur
    raise PlanError("TARGET_INDEX_OUT_OF_RANGE")


def design(start_elev_deg, horizon_s, band, passage_s, prior_phase):
    """Setting branch: elev = 270 - 360*phase. Start at +start_elev, horizon at horizon_s, Rate 1."""
    if not (0.0 < start_elev_deg < 90.0) or horizon_s <= 0.0 or passage_s <= 0.0:
        raise PlanError("DESIGN_INPUTS")
    phase0 = (270.0 - start_elev_deg) / 360.0
    deg_per_s = start_elev_deg / horizon_s
    duration = 360.0 / deg_per_s
    b = max(band, 0.001)
    e_band = math.degrees(math.asin(b))
    out = {
        "phase0": phase0,
        "entry_phase_offset_cycles": frac(phase0 - prior_phase),
        "cycle_duration_seconds": duration,
        "cycle_rate_multiplier": 1.0,
        "animate": True,
        "deg_per_s": deg_per_s,
        "fade_start_s": max(0.0, (start_elev_deg - e_band) / deg_per_s),
        "dark_s": (start_elev_deg + e_band) / deg_per_s,
        "end_elev_deg": start_elev_deg - deg_per_s * passage_s,
        "next_sunrise_s": (start_elev_deg + 180.0) / deg_per_s,
        "band_elev_deg": e_band,
    }
    out["dark_tail_s"] = passage_s - out["dark_s"]
    return out


def timeline(cycle, passage_s, band, azimuth, prior_phase, step_s=1.0):
    rows, t = [], 0.0
    p = dict(cycle, seconds=passage_s)
    while t <= passage_s + 1e-9:
        ph = integrated_phase([dict(p, entry_phase_offset_cycles=prior_phase + cycle["entry_phase_offset_cycles"])],
                              0, t, 0.0)
        el, az = sun_position(ph, azimuth)
        rows.append({"t": round(t, 3), "phase": ph, "elev": el, "az": az, "daylight": daylight(ph, band)})
        t += step_s
    return rows


def plan_refusals(plan, args, rig, passages, p06_index, pin_phase, route_yaw):
    """Every reason APPLY must not run. rig: dict of live rig props. passages: ordered list (see integrated_phase)."""
    r = []
    d = plan
    if not args["start_elev_min"] <= args["start_elev_deg"] <= args["start_elev_max"]:
        r.append("START_ELEV_OUT_OF_BRIEF: %.2f" % args["start_elev_deg"])
    if not args["horizon_min_s"] <= args["horizon_s"] <= args["horizon_max_s"]:
        r.append("HORIZON_OUT_OF_BRIEF: %.2f" % args["horizon_s"])
    if d["dark_s"] > args["dark_by_s"]:
        r.append("DARK_TOO_LATE: daylight reaches 0 at %.2f s > %.2f s (band %.3f)" % (d["dark_s"], args["dark_by_s"],
                                                                                        args["twilight_band"]))
    if d["next_sunrise_s"] <= passage_seconds(passages, p06_index):
        r.append("SUNRISE_INSIDE_P06")
    if p06_index != len(passages) - 1:
        r.append("P06_NOT_LAST: %d Passage(s) after P06 would inherit its phase" % (len(passages) - 1 - p06_index))
    for i, p in enumerate(passages):
        if i == p06_index:
            continue
        if p["animate"]:
            r.append("OTHER_PASSAGE_ANIMATED: %s" % p.get("label", i))
        ph = integrated_phase(passages, i, 0.0, rig["initial_phase_cycles"])
        if abs(wrap180((ph - pin_phase) * 360.0)) > 1e-6:
            r.append("OTHER_PASSAGE_NOT_AT_PIN: %s phase %.6f != pin %.6f" % (p.get("label", i), ph, pin_phase))
        if daylight(ph, args["twilight_band"]) > 0.0:
            r.append("OTHER_PASSAGE_DAYLIT: %s" % p.get("label", i))
    for k in DARK_KEYS:
        if float(rig[k]) != 0.0:
            r.append("NOT_TOTAL_DARK: %s = %s (moon/sky light would light the night)" % (k, rig[k]))
    if rig.get("show_built_in_stars"):
        r.append("NOT_TOTAL_DARK: show_built_in_stars on")
    if not rig.get("use_manual_editor_lighting"):
        r.append("EDITOR_PIN_OFF: editor would follow scrubs (expected use_manual_editor_lighting on)")
    off = abs(wrap180(args_azimuth(args, route_yaw) - route_yaw))
    if off > args["max_off_axis_deg"]:
        r.append("SUN_OFF_AXIS: %.1f deg > %.1f" % (off, args["max_off_axis_deg"]))
    return r


def passage_seconds(passages, index):
    return float(passages[index]["seconds"])


def args_azimuth(args, route_yaw):
    return (route_yaw + float(args["sun_offset_from_route_deg"])) % 360.0


def validate_args(a):
    bad = []
    mode = str(a.get("mode", "")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        bad.append("MODE")
    if a.get("confirm") != "%s %s" % (mode, CONFIRM_SUFFIX):
        bad.append("CONFIRM")
    for k in ("start_elev_deg", "horizon_s", "twilight_band", "sun_lux", "sun_offset_from_route_deg", "dark_by_s",
              "max_off_axis_deg", "start_elev_min", "start_elev_max", "horizon_min_s", "horizon_max_s"):
        v = a.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            bad.append("NUM_%s" % k)
    if not bad:
        if not 0.001 <= a["twilight_band"] <= 1.0:
            bad.append("BAND_RANGE")      # ClampMin/Max [decl CelestialRig.h:207-209]
        if not 0.0 < a["sun_lux"] <= 20.0:
            bad.append("SUN_LUX_RANGE")
    if not isinstance(a.get("passage_guid"), str) or len(a.get("passage_guid") or "") != 32:
        bad.append("PASSAGE_GUID")
    if mode != "DRY" and not a.get("decided_by"):
        bad.append("DECIDED_BY")
    return bad


def rig_target(args, route_yaw):
    return {"apply_manual_lighting_in_game": False, "maximum_sun_intensity": float(args["sun_lux"]),
            "sun_azimuth_degrees": args_azimuth(args, route_yaw), "twilight_altitude_band": float(args["twilight_band"])}


def cycle_target(plan):
    return {k: plan[k] for k in CYCLE_KEYS}


def values_equal(a, b, tol=1e-4):
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def mismatches(live, want, tol=1e-4):
    return {k: (live.get(k), v) for k, v in want.items() if k not in live or not values_equal(live[k], v, tol)}


def probe_gate(samples, plan, args, prior_phase):
    """APPLY probe: each sample's live phase/elevation/daylight vs the offline mirror."""
    bad = []
    cyc = dict(cycle_target(plan), seconds=1e9)
    for s in samples:
        want_phase = integrated_phase([dict(cyc, entry_phase_offset_cycles=prior_phase + plan["entry_phase_offset_cycles"])],
                                      0, s["t"], 0.0)
        if abs(wrap180((s["phase"] - want_phase) * 360.0)) > 0.01:
            bad.append("PROBE_PHASE t=%.2f live %.6f want %.6f" % (s["t"], s["phase"], want_phase))
        if abs(s["daylight"] - daylight(want_phase, args["twilight_band"])) > 1e-3:
            bad.append("PROBE_DAYLIGHT t=%.2f" % s["t"])
        if s.get("sun_elev") is not None and abs(s["sun_elev"] - elevation_deg(want_phase)) > 0.05:
            bad.append("PROBE_SUN_ELEV t=%.2f live %.3f want %.3f" % (s["t"], s["sun_elev"], elevation_deg(want_phase)))
    return bad


def write_record_exclusive(path, data):
    """Create-only, fsynced BEFORE any mutation [prec p06_tail_extend.py:454-460]."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
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


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _parse_guid(text):
    res = unreal.GuidLibrary.parse_string_to_guid(text)       # opening_own_rail.py:456-461 [prec]
    guid, ok = (res if isinstance(res, tuple) else (res, True))
    if not ok or _guid(guid) != text:
        raise PlanError("GUID_PARSE %s" % text)
    return guid


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def _rig():
    rigs = [a for a in _actors() if a.get_class().get_name() == "InfinityStageCelestialRig"]
    if len(rigs) != 1:
        raise PlanError("RIG_COUNT: %d" % len(rigs))
    return rigs[0]


def _read_rig(rig):
    out = {}
    for k in RIG_KEYS + DARK_KEYS + ("initial_phase_cycles", "use_manual_editor_lighting", "editor_preview_time_hours",
                                     "show_built_in_stars"):
        v = rig.get_editor_property(k)
        out[k] = bool(v) if isinstance(v, bool) else float(v)
    return out


def _read_cycles(show):
    rows = []
    for p in show.get_editor_property("passage_settings"):
        c = p.get_editor_property("celestial_cycle")
        rows.append({"label": str(p.get_editor_property("label")), "guid": _guid(p.get_editor_property("passage_guid")),
                     "animate": bool(c.get_editor_property("animate")),
                     "cycle_duration_seconds": float(c.get_editor_property("cycle_duration_seconds")),
                     "cycle_rate_multiplier": float(c.get_editor_property("cycle_rate_multiplier")),
                     "entry_phase_offset_cycles": float(c.get_editor_property("entry_phase_offset_cycles"))})
    return rows


def _write_cycle(show, guid_text, values):
    ps = list(show.get_editor_property("passage_settings"))
    hits = [i for i, p in enumerate(ps) if _guid(p.get_editor_property("passage_guid")) == guid_text]
    if len(hits) != 1:
        raise PlanError("P06_GUID_COUNT: %d" % len(hits))
    p = ps[hits[0]]
    c = p.get_editor_property("celestial_cycle")
    for k in CYCLE_KEYS:
        c.set_editor_property(k, bool(values[k]) if k == "animate" else float(values[k]))
    p.set_editor_property("celestial_cycle", c)
    ps[hits[0]] = p
    show.modify()
    show.set_editor_property("passage_settings", ps)  # struct arrays are copies [prec apply_night_stage1.py:43-46]


def _segments(show):
    """Compiled segments via a transient transport [prec p06_tail_extend.py:548-553]; ticks."""
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    return [{"label": str(s.get_editor_property("label")), "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)} for s in tr.get_editor_property("segments")]


def _route_yaw(label_prefix):
    hits = [a for a in _actors() if a.get_class().get_name() == "InfinityStagePassageActor"
            and str(a.get_actor_label()).startswith(label_prefix)]
    if len(hits) != 1:
        raise PlanError("P06_ACTOR_COUNT: %d" % len(hits))
    sp = hits[0].get_editor_property("route")                   # probe_routes.py:14-19 [prec, meas 5 Oct]
    w = unreal.SplineCoordinateSpace.WORLD
    n = sp.get_spline_length()
    d0, d1 = sp.get_direction_at_distance_along_spline(0, w), sp.get_direction_at_distance_along_spline(n, w)
    return math.degrees(math.atan2(d0.y, d0.x)), math.degrees(math.atan2(d1.y, d1.x))


def _context(rig):
    """Read-only facts the plan does not gate on but the report must carry (exposure, fog, sun light)."""
    def safe(obj, k):
        try:
            v = obj.get_editor_property(k)
            return v if isinstance(v, (bool, int, float, str)) else str(v)
        except Exception as exc:  # noqa: BLE001 - report, never fail on a context read
            return "unreadable: %s" % exc
    out = {"ppv": [], "fog": None, "sun_light": None}
    for a in _actors():
        if a.get_class().get_name() == "PostProcessVolume":
            s = a.get_editor_property("settings")
            out["ppv"].append({"label": str(a.get_actor_label()), "unbound": safe(a, "unbound"),
                               **{k: safe(s, k) for k in ("override_auto_exposure_min_brightness",
                                                          "auto_exposure_min_brightness",
                                                          "override_auto_exposure_max_brightness",
                                                          "auto_exposure_max_brightness", "auto_exposure_bias")}})
    fog = rig.get_editor_property("height_fog_actor")
    if fog is not None:
        c = fog.get_component()
        out["fog"] = {k: safe(c, k) for k in ("fog_density", "enable_volumetric_fog", "volumetric_fog_scattering_distribution",
                                              "directional_inscattering_exponent", "directional_inscattering_start_distance")}
    sun = rig.get_editor_property("sun_light_actor")
    if sun is not None:
        c = sun.get_light_component()
        out["sun_light"] = {"label": str(sun.get_actor_label()),
                            **{k: safe(c, k) for k in ("intensity", "cast_shadows", "volumetric_scattering_intensity",
                                                       "light_source_angle")}}
    out["zz_actors"] = sorted(str(a.get_actor_label()) for a in _actors() if str(a.get_actor_label()).startswith("ZZ_"))
    return out


def _gather(args):
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    if show is None:
        raise PlanError("SHOW_LOAD")
    rig = _rig()
    rows = _read_cycles(show)
    idx = [i for i, r in enumerate(rows) if r["guid"] == args["passage_guid"]]
    if len(idx) != 1:
        raise PlanError("P06_GUID_COUNT: %d" % len(idx))
    tick = float(show.get_editor_property("tick_resolution").numerator) / float(
        show.get_editor_property("tick_resolution").denominator)
    segs = {s["label"]: s for s in _segments(show)}
    for r in rows:
        s = segs.get(r["label"])
        if s is None:
            raise PlanError("SEGMENT_MISSING: %s" % r["label"])
        r["seconds"], r["start_tick"], r["end_tick"] = (s["end"] - s["start"]) / tick, s["start"], s["end"]
    yaw0, yaw1 = _route_yaw(args["passage_actor_prefix"])
    live = _read_rig(rig)
    pin_phase = live["editor_preview_time_hours"] / 24.0
    p06 = idx[0]
    prior = integrated_phase(rows, p06, 0.0, live["initial_phase_cycles"])
    prior = frac(prior - rows[p06]["entry_phase_offset_cycles"])   # P06's own offset is what we set
    plan = design(args["start_elev_deg"], args["horizon_s"], args["twilight_band"], rows[p06]["seconds"], prior)
    if abs(wrap180(yaw1 - yaw0)) > 1.0:
        raise PlanError("P06_ROUTE_NOT_STRAIGHT: %.2f -> %.2f" % (yaw0, yaw1))
    refusals = plan_refusals(plan, args, live, rows, p06, pin_phase, yaw0)
    ctx = _context(rig)
    if ctx["zz_actors"]:
        refusals.append("ZZ_ACTORS_IN_LEVEL: %s (bench temps; level save refused)" % ctx["zz_actors"])
    return {"show": show, "rig": rig, "rows": rows, "p06": p06, "tick": tick, "prior": prior, "plan": plan,
            "route_yaw": yaw0, "rig_live": live, "pin_phase": pin_phase, "refusals": refusals, "context": ctx,
            "rig_target": rig_target(args, yaw0), "cycle_target": cycle_target(plan),
            "timeline": timeline(cycle_target(plan), rows[p06]["seconds"], args["twilight_band"],
                                 args_azimuth(args, yaw0), prior, 2.0)}


def _plain(g):
    return {k: v for k, v in g.items() if k not in ("show", "rig")}


def _backup(run, suffix):
    folder = os.path.join(_project(), "Backups", "PreP06Sunset%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    show_src = os.path.join(_project(), "Content", *SHOW_PATH[len("/Game/"):].split("/")) + ".uasset"
    for src in (show_src, os.path.join(_project(), *UMAP_REL.split("/"))):
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _write_rig(rig, values):
    rig.modify()
    for k, v in values.items():
        rig.set_editor_property(k, bool(v) if isinstance(v, bool) else float(v))


def _sun_state(rig):
    sun = rig.get_editor_property("sun_light_actor")
    r = sun.get_actor_rotation()
    return {"pitch": float(r.pitch), "yaw": float(r.yaw), "roll": float(r.roll),
            "intensity": float(sun.get_light_component().get_editor_property("intensity"))}


def _probe(g, args, run):
    """In-editor evaluation of the real C++ path, then restore the editor pin. Changes only transient rig state and the
    sun/moon/sky/fog values the rig itself writes; the restore must return the sun to its exact before-state."""
    rig, show = g["rig"], g["show"]
    before_sun = _sun_state(rig)
    guid = _parse_guid(args["passage_guid"])
    start = g["rows"][g["p06"]]["start_tick"]
    samples = []
    rig.set_editor_property("use_manual_editor_lighting", False)
    try:
        for t in args["probe_seconds"]:
            ok = bool(rig.evaluate_at_master_frame(show, guid, unreal.FrameNumber(int(round(start + t * g["tick"])))))
            if not ok:
                raise PlanError("PROBE_EVAL_FALSE t=%s" % t)
            st = _sun_state(rig)
            f = forward_vector(st["pitch"], st["yaw"])
            samples.append({"t": float(t), "phase": float(rig.get_editor_property("current_normalized_phase")),
                            "daylight": float(rig.get_editor_property("current_daylight_amount")),
                            "sun_elev": math.degrees(math.asin(max(-1.0, min(1.0, -f[2])))),
                            "sun_az": math.degrees(math.atan2(-f[1], -f[0])) % 360.0, "sun_lux": st["intensity"]})
            unreal.log("%s_PROBE|run=%s|%s" % (MARK, run, json.dumps(samples[-1])))
    finally:
        rig.set_editor_property("use_manual_editor_lighting", True)
        rig.apply_editor_preview_lighting()
    after_sun = _sun_state(rig)
    if mismatches(after_sun, before_sun, 1e-4):
        raise PlanError("PROBE_RESTORE_SUN: %s" % json.dumps(mismatches(after_sun, before_sun, 1e-4)))
    bad = probe_gate(samples, g["plan"], args, g["prior"])
    if bad:
        raise PlanError("PROBE_GATE: " + " || ".join(bad))
    return samples


def _save(run, show, expected_maps):
    dirty = _census()
    if dirty["content"] != [SHOW_PATH] or dirty["maps"] != expected_maps:
        _stop(run, "DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorAssetLibrary.save_loaded_asset(show, False):
        _stop(run, "SHOW_SAVE_FAILED")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD):
        _stop(run, "LEVEL_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "POST_SAVE_DIRTY|" + json.dumps(_census()))


def _readback(args, cycle_want, rig_want):
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    row = [r for r in _read_cycles(show) if r["guid"] == args["passage_guid"]][0]
    live_rig = _read_rig(_rig())
    return mismatches(row, cycle_want, 1e-6), mismatches(live_rig, rig_want, 1e-5)


def run_dry(args, run):
    g = _gather(args)
    path = os.path.join(_here(), DRY_NAME)
    with open(path, "w", encoding="utf-8") as h:
        json.dump(dict(_plain(g), run=run), h, indent=1, sort_keys=True, default=str)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    p = g["plan"]
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|offset=%.6f|duration_s=%.3f|dark_s=%.2f|"
               "azimuth=%.2f|route_yaw=%.2f|report=%s" % (MARK, run, int(not g["refusals"]), len(g["refusals"]),
                                                          p["entry_phase_offset_cycles"], p["cycle_duration_seconds"],
                                                          p["dark_s"], g["rig_target"]["sun_azimuth_degrees"],
                                                          g["route_yaw"], path))
    for x in g["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, x))


def run_apply(args, run):
    g = _gather(args)
    if g["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(g["refusals"]))
    backup = _backup(run, "")
    rp = os.path.join(_here(), RECORD_NAME)
    before_row = {k: g["rows"][g["p06"]][k] for k in CYCLE_KEYS}
    before_rig = {k: g["rig_live"][k] for k in RIG_KEYS}
    rec = {"run": run, "applied": False, "backup": backup, "decided_by": args["decided_by"],
           "before": {"cycle": before_row, "rig": before_rig}, "after": {"cycle": g["cycle_target"], "rig": g["rig_target"]},
           "plan": g["plan"], "prior_phase": g["prior"], "route_yaw": g["route_yaw"]}
    write_record_exclusive(rp, rec)
    unreal.log("%s_BACKUP_OK|run=%s|backup=%s" % (MARK, run, backup))
    _write_cycle(g["show"], args["passage_guid"], g["cycle_target"])
    _write_rig(g["rig"], g["rig_target"])
    bad_c, bad_r = _readback(args, g["cycle_target"], g["rig_target"])
    if bad_c or bad_r:
        _stop(run, "READBACK_PRE_SAVE|%s|%s|NOTHING SAVED; Don't-Save restart" % (bad_c, bad_r))
    if args.get("probe", True):
        try:
            rec["probe"] = _probe(g, args, run)
        except PlanError as exc:
            _stop(run, "%s|NOTHING SAVED; Don't-Save restart" % exc)
    _save(run, g["show"], [EXPECTED_WORLD])
    bad_c, bad_r = _readback(args, g["cycle_target"], g["rig_target"])
    if bad_c or bad_r:
        _stop(run, "READBACK_POST_SAVE|%s|%s" % (bad_c, bad_r))
    rec["applied"] = True
    update_record(rp, rec)
    unreal.log("%s_APPLY_OK|run=%s|show_saved=1|level_saved=1|offset=%.6f|duration_s=%.3f|azimuth=%.2f|sun_lux=%.3f|"
               "band=%.3f|dark_s=%.2f|probe_samples=%d" % (MARK, run, g["plan"]["entry_phase_offset_cycles"],
                                                          g["plan"]["cycle_duration_seconds"],
                                                          g["rig_target"]["sun_azimuth_degrees"], args["sun_lux"],
                                                          args["twilight_band"], g["plan"]["dark_s"],
                                                          len(rec.get("probe") or [])))


def run_revert(args, run):
    rp = os.path.join(_here(), RECORD_NAME)
    if not os.path.exists(rp):
        _stop(run, "NO_RECORD")
    with open(rp, "r", encoding="utf-8") as h:
        rec = json.load(h)
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    rig = _rig()
    row = [r for r in _read_cycles(show) if r["guid"] == args["passage_guid"]][0]
    drift_c, drift_r = mismatches(row, rec["after"]["cycle"], 1e-6), mismatches(_read_rig(rig), rec["after"]["rig"], 1e-5)
    if drift_c or drift_r:
        _stop(run, "DRIFT|%s|%s (live is not what APPLY left; decide by hand)" % (drift_c, drift_r))
    backup = _backup(run, "Revert")
    _write_cycle(show, args["passage_guid"], rec["before"]["cycle"])
    _write_rig(rig, rec["before"]["rig"])
    rig.apply_editor_preview_lighting()
    bad_c, bad_r = _readback(args, rec["before"]["cycle"], rec["before"]["rig"])
    if bad_c or bad_r:
        _stop(run, "REVERT_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (bad_c, bad_r))
    _save(run, show, [EXPECTED_WORLD])
    os.replace(rp, rp + ".reverted-" + run)
    unreal.log("%s_REVERT_OK|run=%s|backup=%s|show_saved=1|level_saved=1" % (MARK, run, backup))


def main():
    args = globals().get("P06SUNSET_ARGS")
    run = datetime.datetime.now().strftime("P06SUN-%Y%m%d-%H%M%S")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as h:
            args = json.load(h)
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    mode = str(args["mode"]).upper()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    early = []
    if editor.get_game_world() is not None:
        early.append("PIE_ACTIVE")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        early.append("SEQUENCER_OPEN")
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if mode != "DRY" and _census() != {"content": [], "maps": []}:
        early.append("DIRTY_BEFORE|" + json.dumps(_census()))
    rp = os.path.join(_here(), RECORD_NAME)
    if mode == "APPLY" and os.path.exists(rp):
        early.append("RECORD_EXISTS")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    unreal.log("%s_START|run=%s|mode=%s" % (MARK, run, mode))
    try:
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
