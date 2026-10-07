"""Offline harness for p06_sunset.py (system Python, no Unreal). Every positive check has a negative control that must
FAIL, so the harness can fail (memory puss-assert-dont-print). Run: python test_p06_sunset_offline.py -> exit 0 and
P06_SUNSET_OFFLINE_OK|pass=N|fail=0.
"""
import importlib.util
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("p06_sunset", os.path.join(HERE, "p06_sunset.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print("%s %s" % ("PASS" if cond else "FAIL", name))


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


ARGS = json.load(open(os.path.join(HERE, "p06_sunset_args.json"), encoding="utf-8"))
P06_S = 3024029 / 24000.0           # P06 Master section [47949592, 50973621) [meas p06_tail_extend_record.json]
FROZEN = {"animate": False, "cycle_duration_seconds": 20.0, "cycle_rate_multiplier": 1.0, "entry_phase_offset_cycles": 0.0}
SECONDS = [100.0, 60.0, 50.0, 50.0, 190.0, P06_S]


def passages(p06_cycle=None, **override):
    rows = [dict(FROZEN, label="Passage %d" % (i + 1), seconds=s) for i, s in enumerate(SECONDS)]
    if p06_cycle:
        rows[5].update(p06_cycle)
    for k, v in override.items():
        i, field = k.split("__")
        rows[int(i)][field] = v
    return rows


RIG = {"initial_phase_cycles": 0.0, "maximum_moon_intensity": 0.0, "day_sky_light_intensity": 0.0,
       "night_sky_light_intensity": 0.0, "show_built_in_stars": False, "use_manual_editor_lighting": True}

# --- 1. Rig mirror: phase -> elevation (CelestialRig.cpp:451-452, 460) ------------------------------------------------
for ph, el in ((0.0, -90.0), (0.25, 0.0), (0.5, 90.0), (0.75, 0.0), (0.7305555555, 7.0), (0.8, -18.0)):
    check("elev(%.4f)=%.1f" % (ph, el), near(m.elevation_deg(ph), el, 1e-4))
for ph in (0.55, 0.62, 0.74, 0.79, 0.93):
    check("setting branch linear at %.2f" % ph, near(m.elevation_deg(ph), 270.0 - 360.0 * ph, 1e-6))
    el, az = m.sun_position(ph, 30.0)
    check("rotator->sun elevation agrees at %.2f" % ph, near(el, m.elevation_deg(ph), 1e-6))
check("afternoon sun stands AT SunAzimuthDegrees", near(m.sun_position(0.7, 30.0)[1], 30.0, 1e-6))
check("morning sun stands opposite (az+180)", near(m.sun_position(0.3, 30.0)[1], 210.0, 1e-6))
# negative control: a mutant mapping (sin instead of -cos) must disagree with the rig mirror
mutant = lambda ph: math.degrees(math.asin(math.sin(2 * math.pi * ph)))
check("NEG mutant elevation mapping is detected", not near(mutant(0.7305555555), 7.0, 1e-3))

# --- 2. Daylight / moon (SmoothStep band) ------------------------------------------------------------------------------
check("daylight at horizon = 0.5", near(m.daylight(0.75, 0.05), 0.5))
check("daylight 1 at +7 deg (band 0.05)", near(m.daylight(0.7305555555, 0.05), 1.0))
check("daylight 0 at midnight", m.daylight(0.0, 0.05) == 0.0 and m.daylight(0.0, 0.12) == 0.0)
check("moonlight full at midnight (why MaximumMoonIntensity must be 0)", near(m.moonlight(0.0, 0.05), 1.0))
check("NEG daylight NOT 0 just above the band", m.daylight(0.75 + (math.degrees(math.asin(0.05)) - 0.1) / 360.0, 0.05) > 0.0)

# --- 3. Design -------------------------------------------------------------------------------------------------------
d = m.design(ARGS["start_elev_deg"], ARGS["horizon_s"], ARGS["twilight_band"], P06_S, 0.0)
cyc = dict(m.cycle_target(d), seconds=P06_S)
rows = passages(m.cycle_target(d))
ph = lambda t: m.integrated_phase(rows, 5, t, 0.0)
check("start elevation 7.0 via the Compiler mirror", near(m.elevation_deg(ph(0.0)), 7.0, 1e-6))
check("horizon at 37 s", near(m.elevation_deg(ph(37.0)), 0.0, 1e-6))
check("fully dark by %.2f s" % d["dark_s"], m.daylight(ph(d["dark_s"] + 1e-3), 0.05) == 0.0)
check("NEG still lit 1 s before dark_s", m.daylight(ph(d["dark_s"] - 1.0), 0.05) > 0.0)
check("dark_s within brief (<= 60 s)", d["dark_s"] <= 60.0)
check("full intensity until fade_start (~21.9 s)", near(m.daylight(ph(d["fade_start_s"] - 0.01), 0.05), 1.0))
check("end of P06 below band, no sunrise", m.elevation_deg(ph(P06_S)) < -d["band_elev_deg"] and d["next_sunrise_s"] > P06_S)
check("elapsed clamps at segment end (Scene 6 holds the dark end state)", near(ph(P06_S + 500.0), ph(P06_S)))
check("duration ~1902.86 s, offset ~0.730556",
      near(d["cycle_duration_seconds"], 1902.857142857, 1e-6) and near(d["entry_phase_offset_cycles"], 0.7305555556, 1e-9))
dp = m.design(7.0, 37.0, 0.05, P06_S, 0.25)
check("offset compensates a non-zero prior phase", near(m.frac(0.25 + dp["entry_phase_offset_cycles"]), dp["phase0"], 1e-12))
d12 = m.design(7.0, 37.0, 0.12, P06_S, 0.0)
check("band 0.12 (current global) darkens only at ~73.4 s", near(d12["dark_s"], 73.43, 0.01))

# --- 4. Integration across Passages (Compiler.cpp:432-470) -----------------------------------------------------------
check("frozen prior Passages contribute 0", all(near(m.integrated_phase(rows, i, 30.0, 0.0), 0.0) for i in range(5)))
anim = passages(m.cycle_target(d), **{"2__animate": True})
check("NEG an animated earlier Passage shifts P06 start", not near(m.integrated_phase(anim, 5, 0.0, 0.0), d["phase0"], 1e-6))

# --- 5. Plan refusals ------------------------------------------------------------------------------------------------
ok_args = dict(ARGS)
check("plan clean for the shipped args, route yaw 0", m.plan_refusals(d, ok_args, RIG, rows, 5, 0.0, 0.0) == [])
check("azimuth = route + 30", near(m.args_azimuth(ok_args, 0.0), 30.0))
r = m.plan_refusals(d, dict(ok_args, sun_offset_from_route_deg=278.8086), RIG, rows, 5, 0.0, 0.0)
check("NEG current SunAzimuth 278.8 refused (81.2 deg off-axis)", any(x.startswith("SUN_OFF_AXIS: 81.2") for x in r))
r = m.plan_refusals(d, ok_args, dict(RIG, maximum_moon_intensity=0.2), rows, 5, 0.0, 0.0)
check("NEG moon > 0 refused", any("maximum_moon_intensity" in x for x in r))
r = m.plan_refusals(d, ok_args, dict(RIG, night_sky_light_intensity=0.035), rows, 5, 0.0, 0.0)
check("NEG night sky light > 0 refused", any("night_sky_light_intensity" in x for x in r))
r = m.plan_refusals(d, ok_args, RIG, anim, 5, 0.0, 0.0)
check("NEG animated other Passage refused", any(x.startswith("OTHER_PASSAGE_ANIMATED") for x in r))
r = m.plan_refusals(d, ok_args, RIG, rows + [dict(FROZEN, label="Passage 7", seconds=30.0)], 5, 0.0, 0.0)
check("NEG a Passage after P06 refused", any(x.startswith("P06_NOT_LAST") for x in r))
r = m.plan_refusals(d, ok_args, dict(RIG, initial_phase_cycles=0.25), rows, 5, 0.0, 0.0)
check("NEG initial phase 0.25 (sunrise) refused for other Passages", any(x.startswith("OTHER_PASSAGE_NOT_AT_PIN") for x in r))
r = m.plan_refusals(d12, dict(ok_args, twilight_band=0.12), RIG, rows, 5, 0.0, 0.0)
check("NEG band 0.12 refused by dark_by_s 60", any(x.startswith("DARK_TOO_LATE") for x in r))
r = m.plan_refusals(m.design(10.0, 37.0, 0.05, P06_S, 0.0), dict(ok_args, start_elev_deg=10.0), RIG, rows, 5, 0.0, 0.0)
check("NEG start elevation 10 refused", any(x.startswith("START_ELEV") for x in r))

# --- 6. Probe gate ---------------------------------------------------------------------------------------------------
good = [{"t": t, "phase": ph(t), "daylight": m.daylight(ph(t), 0.05), "sun_elev": m.elevation_deg(ph(t))}
        for t in ARGS["probe_seconds"]]
check("probe gate passes the mirror's own samples", m.probe_gate(good, d, ok_args, 0.0) == [])
bad = [dict(s, phase=s["phase"] + 0.01, sun_elev=s["sun_elev"] - 3.6) for s in good]
check("NEG probe gate fails a 3.6 deg phase error", len(m.probe_gate(bad, d, ok_args, 0.0)) >= len(good))

# --- 7. Args, record ---------------------------------------------------------------------------------------------------
check("shipped args validate (DRY)", m.validate_args(ARGS) == [])
check("NEG wrong confirm refused", "CONFIRM" in m.validate_args(dict(ARGS, mode="APPLY")))
check("NEG APPLY without decided_by refused",
      "DECIDED_BY" in m.validate_args(dict(ARGS, mode="APPLY", confirm="APPLY P06SUNSET")))
check("NEG band out of clamp refused", "BAND_RANGE" in m.validate_args(dict(ARGS, twilight_band=0.0)))
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "rec.json")
    m.write_record_exclusive(p, {"a": 1})
    try:
        m.write_record_exclusive(p, {"a": 2})
        second = True
    except FileExistsError:
        second = False
    check("NEG record is create-only", not second and json.load(open(p))["a"] == 1)
check("mismatches flags a changed field only", m.mismatches({"x": 1.0, "y": True}, {"x": 1.0, "y": False}) == {"y": (True, False)})

# --- report ----------------------------------------------------------------------------------------------------------
print("DESIGN|" + json.dumps({k: round(v, 6) if isinstance(v, float) else v for k, v in d.items()}))
for row in m.timeline(m.cycle_target(d), P06_S, 0.05, 30.0, 0.0, 10.0):
    print("T|t=%6.1f|elev=%7.3f|az=%6.2f|daylight=%.3f" % (row["t"], row["elev"], row["az"], row["daylight"]))
fails = [n for n, ok in RESULTS if not ok]
print("P06_SUNSET_OFFLINE_%s|pass=%d|fail=%d" % ("OK" if not fails else "FAILED", len(RESULTS) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
