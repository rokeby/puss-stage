"""TOPPLE CORE (7 Oct, offline-written, NEVER RUN IN UNREAL): pure logic for P06 "STILL + CHAIN":
  STILL  every P06 row at rest except ONE keeper row (Gary 7 Oct: "all of p06 can stand still leaving eerie silence
         except maybe one wing somewhere still sliding towards the back");
  CHAIN  an N-slab (default 6) domino chain falling away from the camera on consecutive rows, one side (variant C,
         "Keep going with 6"), timed to a target final impact in P06 seconds ("just before sun goes dusk").

No `unreal` import here: everything in this file runs in system Python and is exercised by test_topple_apply.py.
topple_apply.py (editor side) and make_keys.py (offline solver step) both load this file by path.

Tiers per claim: [decl] read in a file/header we can open (cited), [bin] recovered from an installed DLL,
[prec] an in-repo precedent call (cited; whether it ran), [inf] inferred (why).

Facts this file encodes
  * Phase law, OneShot: Phase = clamp(PhaseOffsetCycles + (MasterFrame - Origin)/Tick * CycleRateHz, 0, 1); Origin =
    the compiled wing's PassFrame for PhaseOrigin=PassFrame [decl InfinityStagePassageActor.cpp:1378-1431].
  * PassFrame = the frame at which the compiled camera distance reaches the cue's station DistanceCm: the compiler
    walks FirstPassFrame/LeadInDistanceCm then += IntervalToNext / GapToNextCm per cue [decl
    InfinityStageCompiler.cpp:254-288] and EvaluateDistanceAtFrame interpolates linearly between those pass points
    [decl :397-410]. So PassFrame is the camera at the cue's STATION, not at the panel's hinge; the hinge may sit off
    the station by LocalTransform/OccurrenceOffset/bounds (DRY measures that delta per row).
  * Curve text: FRuntimeFloatCurve = {UPROPERTY() FRichCurve EditorCurveData; ExternalCurve}
    [decl UE_5.8 Curves/CurveFloat.h:12-20]; FRichCurve.Keys [decl RichCurve.h:355]; FRichCurveKey fields
    InterpMode/TangentMode/TangentWeightMode/Time/Value (Edit) + ArriveTangent/ArriveTangentWeight/LeaveTangent/
    LeaveTangentWeight (UPROPERTY() only) [decl RichCurve.h:79-117]. EditorCurveData has no Edit/BP flag, so Python
    get/set_editor_property on it is [inf] unavailable; the struct text route (StructBase.export_text/import_text)
    exists [bin UnrealEditor-PythonScriptPlugin.dll: "import_text(self, content: str) -> bool -- imports the provided
    string into the Unreal struct"] and text export/import does not need Edit flags [inf: UE ShouldPort semantics; DRY
    MEASURES a round-trip on a free-standing struct before APPLY may run].
  * Defaults when a key field is omitted from export text (delta export): InterpMode RCIM_Linear, TangentMode RCTM_Auto,
    TangentWeightMode RCTWM_WeightedNone, numbers 0 [decl RichCurve.h:119-124 constructor].
"""
import hashlib
import json
import math

MARK = "FLATV3_TOPPLE"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"              # p6_ceiling_off.py:11 [prec, ran 4 Oct]
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"  # p6_ceiling_off.py:12
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"  # p01_note_lamps.py:92
SHOW_FILE_REL = "Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
UMAP_FILE_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
P06_GUID = "9BFC29C45D47911FF7836BB8537230D2"   # p6_ceiling_off.py:14; p06_sunset_dry.json rows[-1] label "Passage 6"
P06_LABEL = "Passage 6"
N_ROWS = 6                                     # Gary 7 Oct: "Keep going with 6"
MAX_ANGLE_DEG = -90.0                          # Gary: away from the camera; negative = away [decl Types.h:665-674]
OVERRIDE_MECHANISM_RATE = 1 << 2               # [decl InfinityStageTypes.h:596]
OVERRIDE_MECHANISM_PHASE = 1 << 3              # [decl InfinityStageTypes.h:599]
SIDES = ("L", "R")

# Eligibility thresholds (a slab model needs a thin, tall, laterally hinged panel)
MAX_THICKNESS_CM = 50.0
MIN_HEIGHT_CM = 300.0
MAX_AXIS_DOT = 0.1                             # same threshold the C++ uses for a degenerate hinge [decl .cpp:217]
SPACING_TOL_CM = 10.0                          # solver takes one spacing [decl topple_solver.py:48]
MIN_LATERAL_OVERLAP_CM = 100.0
FLAT_EPS = 1e-4
DEFAULT_LEAD_CM = 3000.0                       # brief: creak with the camera ~30 m before the first row

KEY_DEFAULTS = {"InterpMode": "RCIM_Linear", "TangentMode": "RCTM_Auto", "TangentWeightMode": "RCTWM_WeightedNone",
                "Time": 0.0, "Value": 0.0, "ArriveTangent": 0.0, "ArriveTangentWeight": 0.0,
                "LeaveTangent": 0.0, "LeaveTangentWeight": 0.0}


# API-probe curve (DRY imports it into a FREE-STANDING RuntimeFloatCurve, never into the Show): break + user tangents
PROBE_SOLVER_KEYS = [
    {"phase": 0.0, "value": 0.0, "arrive_tangent": 0.0, "leave_tangent": 0.000741},
    {"phase": 0.186335, "value": 0.021111, "arrive_tangent": 0.000513, "leave_tangent": 0.138745},
    {"phase": 0.491635, "value": 0.293593, "arrive_tangent": 2.78959, "leave_tangent": 1.228727},
    {"phase": 0.81101, "value": 0.982509, "arrive_tangent": 2.163351, "leave_tangent": -0.583558},
    {"phase": 1.0, "value": 0.982509, "arrive_tangent": 0.0, "leave_tangent": 0.0},
]   # = variant_C_chain4_away.json rows[0].keys[0,3,5,9,14] (7 Oct solver output)
EVAL_TOL = 2e-3      # normalised; 0.18 deg at 90 deg


class PlanError(Exception):
    pass


def require(cond, reason):
    if not cond:
        raise PlanError(reason)


# =====================================================================================================================
# Args / confirm
# =====================================================================================================================

def confirm_for(mode, plan_doc=None, originals_doc=None):
    if mode == "DRY":
        return "DRY TOPPLE P06"
    if mode == "APPLY":
        require(plan_doc is not None, "APPLY_NEEDS_PLAN_JSON")
        return "APPLY TOPPLE " + plan_doc["confirm_token"]
    if mode == "REVERT":
        require(originals_doc is not None, "REVERT_NEEDS_ORIGINALS_JSON")
        return "REVERT TOPPLE " + originals_doc["run_id"]
    raise PlanError("MODE_INVALID: %r" % (mode,))


def validate_args(args, plan_doc=None, originals_doc=None):
    mode = str(args.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID: %r" % (mode,))
    want = confirm_for(mode, plan_doc, originals_doc)
    require(args.get("confirm") == want, "CONFIRM_MISMATCH: %r, want %r" % (args.get("confirm"), want))
    if mode == "APPLY":
        require(str(args.get("decided_by") or "").strip(), "NOT_DECIDED: decided_by is empty (a Show + level write)")
        require(plan_doc.get("gates_ok") is True, "PLAN_GATES_FAILED: %s" % plan_doc.get("refusals"))
        hits = (plan_doc.get("chain") or {}).get("next_row_hits") or []
        if hits and not args.get("ack_next_row_intersection"):
            raise PlanError("NEXT_ROW_INTERSECTION_NOT_ACKED: %s" % json.dumps(hits))
    return mode


def confirm_token(parts, side, guids, inputs_hash):
    chain = ("%s %s..%s " % (side, guids[0][:8], guids[-1][:8])) if guids else ""
    return "P06 %s %s#%s" % ("+".join(parts), chain, inputs_hash[:8])


# =====================================================================================================================
# UE struct text (export_text / import_text form): "(A=1,B=(C=2),D="x,y",E=NSLOCTEXT("a","b","c"))"
# =====================================================================================================================

def _scan_top(text):
    """Split the inside of a parenthesised struct text into top-level 'Name=Value' items (quote/paren aware)."""
    s = text.strip()
    require(s.startswith("(") and s.endswith(")"), "STRUCT_TEXT_NOT_PARENTHESISED: %r" % s[:60])
    body = s[1:-1]
    items, depth, quote, start, i = [], 0, False, 0, 0
    while i < len(body):
        ch = body[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                quote = False
        elif ch == '"':
            quote = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            require(depth >= 0, "STRUCT_TEXT_UNBALANCED")
        elif ch == "," and depth == 0:
            items.append(body[start:i])
            start = i + 1
        i += 1
    require(depth == 0 and not quote, "STRUCT_TEXT_UNBALANCED")
    if body[start:].strip():
        items.append(body[start:])
    return [it.strip() for it in items if it.strip()]


def fields(text):
    """Ordered [(name, value_text)] of a struct text. Array items (no '=') get name None."""
    out = []
    for item in _scan_top(text):
        depth, quote, eq = 0, False, -1
        for i, ch in enumerate(item):
            if ch == '"':
                quote = not quote
            elif not quote and ch == "(":
                depth += 1
            elif not quote and ch == ")":
                depth -= 1
            elif not quote and depth == 0 and ch == "=":
                eq = i
                break
        out.append((item[:eq].strip(), item[eq + 1:].strip()) if eq > 0 else (None, item))
    return out


def get_field(text, name):
    for k, v in fields(text):
        if k == name:
            return v
    return None


def without_fields(text, names):
    return "(" + ",".join(("%s=%s" % (k, v)) if k is not None else v
                          for k, v in fields(text) if k not in names) + ")"


def replace_field(text, name, value):
    found = False
    parts = []
    for k, v in fields(text):
        if k == name:
            v, found = value, True
        parts.append(("%s=%s" % (k, v)) if k is not None else v)
    require(found, "FIELD_MISSING: %s" % name)
    return "(" + ",".join(parts) + ")"


def cue_text_outside_mechanism(cue_text):
    """A cue's export text with WingPair.Mechanism and WingPair.LocalOverrideMask blanked: what APPLY may not change."""
    wp = get_field(cue_text, "WingPair")
    require(wp is not None, "CUE_TEXT_NO_WINGPAIR")
    return replace_field(cue_text, "WingPair", without_fields(wp, ("Mechanism", "LocalOverrideMask")))


def mechanism_outside_planned(mech_text, action):
    """Mechanism export text with every field APPLY writes for this action blanked (the rest must be unchanged).
    action: "still" | "chain"."""
    if action == "still":
        return without_fields(mech_text, ("PlaybackMode", "PhaseOffsetCycles"))
    return without_fields(mech_text, ("Kind", "PlaybackMode", "CycleRateHz", "PhaseOrigin", "PhaseOffsetCycles",
                                      "MaxAngleDeg", "LeftNormalizedCurve", "RightNormalizedCurve",
                                      "bTopFollowsMechanism"))


def _num(text):
    return float(str(text).strip().rstrip("fF"))


def parse_curve_keys(curve_text):
    """Keys of an FRuntimeFloatCurve export text, every field filled with its C++ default when omitted."""
    if curve_text is None:
        return []
    ecd = get_field(curve_text, "EditorCurveData")
    if ecd is None:
        return []
    keys_text = get_field(ecd, "Keys")
    if keys_text is None or keys_text.strip() in ("", "()"):
        return []
    out = []
    for _, item in fields(keys_text):
        row = dict(KEY_DEFAULTS)
        for k, v in fields(item):
            require(k in KEY_DEFAULTS, "UNKNOWN_KEY_FIELD: %s" % k)
            row[k] = v.strip() if isinstance(KEY_DEFAULTS[k], str) else _num(v)
        out.append(row)
    return out


def external_curve(curve_text):
    v = get_field(curve_text, "ExternalCurve") if curve_text else None
    return None if v is None or v.strip() in ("None", "", '""') else v.strip()


def _fmt(x):
    return "%.9f" % float(x)


def plan_keys(solver_keys):
    """Solver keys (phase, value, arrive_tangent, leave_tangent; normalised) -> RichCurve key dicts.
    Cubic everywhere; RCTM_Break where arrive != leave (impacts, snag), RCTM_User elsewhere (both keep our tangents;
    Auto would recompute them)."""
    out = []
    for k in solver_keys:
        a, l = float(k["arrive_tangent"]), float(k["leave_tangent"])
        out.append({"InterpMode": "RCIM_Cubic", "TangentMode": "RCTM_Break" if abs(a - l) > 1e-6 else "RCTM_User",
                    "TangentWeightMode": "RCTWM_WeightedNone", "Time": float(k["phase"]), "Value": float(k["value"]),
                    "ArriveTangent": a, "ArriveTangentWeight": 0.0, "LeaveTangent": l, "LeaveTangentWeight": 0.0})
    times = [k["Time"] for k in out]
    require(times == sorted(times) and len(set(times)) == len(times), "KEY_TIMES_NOT_STRICTLY_SORTED")
    require(out and abs(out[0]["Time"]) < 1e-9 and abs(out[-1]["Time"] - 1.0) < 1e-9, "KEYS_MUST_SPAN_PHASE_0_1")
    return out


def curve_text(keys):
    parts = []
    for k in keys:
        parts.append("(InterpMode=%s,TangentMode=%s,TangentWeightMode=%s,Time=%s,Value=%s,ArriveTangent=%s,"
                     "ArriveTangentWeight=%s,LeaveTangent=%s,LeaveTangentWeight=%s)" % (
                         k["InterpMode"], k["TangentMode"], k["TangentWeightMode"], _fmt(k["Time"]), _fmt(k["Value"]),
                         _fmt(k["ArriveTangent"]), _fmt(k["ArriveTangentWeight"]), _fmt(k["LeaveTangent"]),
                         _fmt(k["LeaveTangentWeight"])))
    return "(EditorCurveData=(Keys=(%s)),ExternalCurve=None)" % ",".join(parts)


def flat_keys():
    """The chain row's OTHER side: an explicit zero curve. Kind and PlaybackMode are per row [decl Types.h:647-674],
    so the other side would otherwise topple along its old undulation curve."""
    k = dict(KEY_DEFAULTS, InterpMode="RCIM_Linear", TangentMode="RCTM_User")
    return [dict(k, Time=0.0), dict(k, Time=1.0)]


def keys_match(planned, actual, tol=2e-6):
    """Exact enum match, float32-tolerant numbers. Returns [] or a list of differences."""
    diffs = []
    if len(planned) != len(actual):
        return ["KEY_COUNT %d != %d" % (len(actual), len(planned))]
    for i, (p, a) in enumerate(zip(planned, actual)):
        for f in ("InterpMode", "TangentMode", "TangentWeightMode"):
            if str(a[f]).split(".")[-1].upper().replace("_", "") != str(p[f]).upper().replace("_", ""):
                diffs.append("key%d.%s %s != %s" % (i, f, a[f], p[f]))
        for f in ("Time", "Value", "ArriveTangent", "LeaveTangent"):
            if abs(float(a[f]) - float(p[f])) > tol * max(1.0, abs(float(p[f]))):
                diffs.append("key%d.%s %r != %r" % (i, f, a[f], p[f]))
    return diffs


def hermite(keys, t):
    """RichCurve cubic segment as the solver fits it (topple_solver.py:248-269): Hermite, tangents per curve-time unit,
    scaled by the segment length. Held flat outside the keys. Whether UE's FRichCurve::Eval equals this is [inf]
    offline; DRY and APPLY MEASURE it with MathLibrary.get_runtime_float_curve_value [decl KismetMathLibrary.h:857-858]."""
    if not keys:
        return 0.0
    if t <= keys[0]["Time"]:
        return keys[0]["Value"]
    if t >= keys[-1]["Time"]:
        return keys[-1]["Value"]
    for k0, k1 in zip(keys[:-1], keys[1:]):
        if k0["Time"] <= t <= k1["Time"]:
            d = k1["Time"] - k0["Time"]
            u = (t - k0["Time"]) / d
            h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
            h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
            return h00 * k0["Value"] + h10 * d * k0["LeaveTangent"] + h01 * k1["Value"] + h11 * d * k1["ArriveTangent"]
    return keys[-1]["Value"]


def sample_phases(keys, step=0.02):
    ph = {round(i * step, 6) for i in range(int(round(1 / step)) + 1)}
    for k0, k1 in zip(keys[:-1], keys[1:]):
        ph.add(round(k0["Time"], 6))
        ph.add(round((k0["Time"] + k1["Time"]) / 2, 6))
    return sorted(ph)


# =====================================================================================================================
# Compiled route law (mirror of InfinityStageCompiler.cpp:254-288, :385-410), frames relative to the segment start
# =====================================================================================================================

def route_law(lead_in_frames, lead_in_cm, rows, tail_frames, tail_cm):
    """rows: [(interval_ticks, gap_cm)] in cue order (the last row's interval/gap are not used).
    Returns {"points": [(frame, cm)...], "stations": [(pass_frame, cm)], "segment_end": frame}."""
    require(rows, "ROUTE_NO_ROWS")
    pts = [(0, 0.0)]
    f, d = int(lead_in_frames), float(lead_in_cm)
    stations = []
    for i, (iv, gap) in enumerate(rows):
        stations.append((f, d))
        if i < len(rows) - 1:
            require(int(iv) > 0 and float(gap) > 0, "ROUTE_NONPOSITIVE_STEP row %d" % i)
            f, d = f + int(iv), d + float(gap)
    pts += [(sf, sd) for sf, sd in stations]
    end = (f + int(tail_frames), d + float(tail_cm))
    pts.append(end)
    return {"points": pts, "stations": stations, "segment_end": end[0], "total_cm": end[1]}


def distance_at_frame(law, frame):
    pts = law["points"]
    if frame <= pts[0][0]:
        return pts[0][1]
    for (f0, d0), (f1, d1) in zip(pts[:-1], pts[1:]):
        if frame <= f1:
            if f1 <= f0:
                return d1
            return d0 + (d1 - d0) * (frame - f0) / float(f1 - f0)
    return pts[-1][1]


def frame_at_distance(law, cm):
    pts = law["points"]
    require(cm >= pts[0][1] - 1e-6, "DISTANCE_BEFORE_SEGMENT_START: %.1f cm" % cm)
    for (f0, d0), (f1, d1) in zip(pts[:-1], pts[1:]):
        if cm <= d1 + 1e-9:
            if d1 - d0 <= 1e-9:
                return float(f0)
            return f0 + (f1 - f0) * (cm - d0) / (d1 - d0)
    raise PlanError("DISTANCE_PAST_SEGMENT_END: %.1f cm" % cm)


def speed_at_distance(law, cm, tick):
    pts = law["points"]
    for (f0, d0), (f1, d1) in zip(pts[:-1], pts[1:]):
        if cm <= d1 + 1e-9 and f1 > f0:
            return (d1 - d0) / ((f1 - f0) / float(tick)) / 100.0
    return None


# =====================================================================================================================
# Eligibility, windows, hash
# =====================================================================================================================

def is_static(mech):
    return "STATIC" in str(mech.get("playback_mode", "")).upper()


def at_rest_now(row):
    """Already at rest: Static AND every curve is ~0 at its PhaseOffsetCycles. Static evaluates the curve at
    PhaseOffsetCycles (+ the section's PhaseBias) with no time term [decl PassageActor.cpp:1424-1428], so a Static row
    with offset 0.333 on the undulation curve would HOLD a 75 % slide (measured offline on the live exports)."""
    return is_static(row["mechanism"]) and abs(float(row["mechanism"].get("phase_offset_cycles", 0.0))) < 1e-12 and \
        all(abs(float(v)) <= FLAT_EPS for v in row.get("curve_at0", {}).values())


def side_reasons(row, side, keeper_guid=None):
    """Why one (row, side) cannot be a chain slab; [] = eligible. Moving rows are allowed (STILL stops them);
    the row's other side is overwritten with a zero curve by the chain write."""
    r = []
    s = row["sides"].get(side)
    if not row.get("enabled", True):
        r.append("CUE_DISABLED")
    if keeper_guid and row["cue_guid"] == keeper_guid:
        r.append("KEEPER_ROW")
    if s is None or not s.get("mesh"):
        return r + ["NO_PANEL"]
    if s.get("materialized") is not True:
        r.append("NOT_MATERIALIZED")
    if "CAMERA_GUST" in str(row["mechanism"].get("playback_mode", "")).upper():
        r.append("CAMERA_GUST_ROW")
    if s.get("upright") is False:
        r.append("PANEL_NOT_UPRIGHT (height = bounds Z assumes an upright base)")
    if s.get("external_curve"):
        r.append("EXTERNAL_CURVE_SET (it overrides EditorCurveData) %s" % s["external_curve"])
    if float(s["thickness_cm"]) > MAX_THICKNESS_CM:
        r.append("TOO_THICK_FOR_SLAB: %.1f cm" % s["thickness_cm"])
    if float(s["height_cm"]) < MIN_HEIGHT_CM:
        r.append("TOO_SHORT: %.1f cm" % s["height_cm"])
    if abs(float(s["axis_dot_tangent"])) > MAX_AXIS_DOT:
        r.append("HINGE_AXIS_NOT_LATERAL: dot %.3f" % s["axis_dot_tangent"])
    return r


def _overlap(a, b):
    return min(a["lateral_max_cm"], b["lateral_max_cm"]) - max(a["lateral_min_cm"], b["lateral_min_cm"])


def window_report(rows, start, side, n=N_ROWS, keeper_guid=None):
    """n consecutive rows (route order) on one side + what stops the last slab. refusals[] / flags[]."""
    win = rows[start:start + n]
    rep = {"start_ordinal": start, "side": side, "n": n, "cue_guids": [w["cue_guid"] for w in win],
           "labels": [w["label"] for w in win], "refusals": [], "flags": []}
    if len(win) < n:
        rep["refusals"].append("PAST_PASSAGE_END")
        return rep
    for w in win:
        for reason in side_reasons(w, side, keeper_guid):
            rep["refusals"].append("%s %s: %s" % (w["label"], side, reason))
    if rep["refusals"]:
        return rep
    sm = [w["sides"][side] for w in win]
    hinge = [float(m["hinge_route_cm"]) for m in sm]
    gaps = [b - a for a, b in zip(hinge[:-1], hinge[1:])]
    rep.update({"heights_cm": [round(m["height_cm"], 2) for m in sm],
                "thickness_cm": [round(m["thickness_cm"], 2) for m in sm],
                "hinge_route_cm": [round(h, 2) for h in hinge], "gaps_cm": [round(g, 2) for g in gaps],
                "lateral_inner_cm": [round(min(abs(m["lateral_min_cm"]), abs(m["lateral_max_cm"])), 1) for m in sm],
                "lateral_width_cm": [round(m["lateral_max_cm"] - m["lateral_min_cm"], 1) for m in sm],
                "meshes": [m["mesh"] for m in sm]})
    if any(g <= 0 for g in gaps):
        rep["refusals"].append("HINGES_NOT_INCREASING_ALONG_ROUTE %s" % gaps)
        return rep
    for k in range(n - 1):
        c = (sm[k]["thickness_cm"] + sm[k + 1]["thickness_cm"]) / 2.0
        if sm[k]["height_cm"] <= gaps[k] - c:
            rep["refusals"].append("NO_CONTACT: row %d height %.0f <= gap %.0f - c" % (k, sm[k]["height_cm"], gaps[k]))
        if _overlap(sm[k], sm[k + 1]) < MIN_LATERAL_OVERLAP_CM:
            rep["refusals"].append("LATERAL_OVERLAP %.0f cm < %.0f between rows %d and %d" % (
                _overlap(sm[k], sm[k + 1]), MIN_LATERAL_OVERLAP_CM, k, k + 1))
    # what the last slab meets: the next same-side panel (static under STILL) -> braced end
    last = sm[-1]
    nxt = None
    for w in rows[start + n:]:
        o = w["sides"].get(side)
        if o and o.get("mesh"):
            nxt = (w, o)
            break
    hits = []
    for w in rows[start + n:]:
        o = w["sides"].get(side)
        if o and o.get("mesh") and float(o["hinge_route_cm"]) <= hinge[-1] + last["height_cm"]:
            hits.append({"label": w["label"], "cue_guid": w["cue_guid"], "hinge_route_cm": round(o["hinge_route_cm"], 1),
                         "height_cm": round(o["height_cm"], 1), "thickness_cm": round(o["thickness_cm"], 1),
                         "mesh": o["mesh"]})
    rep["floor_end_hits"] = hits
    brace = None
    if nxt is not None:
        w, o = nxt
        gap = float(o["hinge_route_cm"]) - hinge[-1]
        c = (last["thickness_cm"] + o["thickness_cm"]) / 2.0
        reach = last["height_cm"] >= gap - c
        brace = {"label": w["label"], "cue_guid": w["cue_guid"], "hinge_route_cm": round(o["hinge_route_cm"], 2),
                 "thickness_cm": round(o["thickness_cm"], 2), "height_cm": round(o["height_cm"], 2),
                 "gap_cm": round(gap, 2), "reached": reach, "mesh": o["mesh"],
                 "lateral_overlap_cm": round(_overlap(last, o), 1)}
        if reach:
            ang = math.asin(max(-1.0, min(1.0, (gap - c) / last["height_cm"])))
            brace["contact_deg"] = round(math.degrees(ang), 2)
            brace["contact_height_cm"] = round(last["height_cm"] * math.cos(ang), 1)
            if brace["contact_height_cm"] > o["height_cm"]:
                brace["problem"] = "SLAB_TIP_PASSES_OVER_BRACE (contact %.0f cm > brace %.0f cm)" % (
                    brace["contact_height_cm"], o["height_cm"])
            elif brace["lateral_overlap_cm"] < MIN_LATERAL_OVERLAP_CM:
                brace["problem"] = "BRACE_LATERAL_OVERLAP %.0f cm" % brace["lateral_overlap_cm"]
    rep["brace"] = brace
    if hits:
        rep["flags"].append("FLOOR_END_LIES_THROUGH %d standing same-side panel(s) within %.0f cm" % (
            len(hits), last["height_cm"]))
    return rep


def eligible_windows(rows, n=N_ROWS, keeper_guid=None):
    reports = [window_report(rows, i, side, n, keeper_guid) for side in SIDES for i in range(len(rows))]
    ok = [r for r in reports if not r["refusals"]]
    counts = {}
    for r in reports:
        for reason in r["refusals"]:
            key = reason.split(": ", 1)[-1].split(":")[0].split(" ")[0]
            counts[key] = counts.get(key, 0) + 1
    return ok, counts


def default_keeper(rows, tick, dark_s=52.0):
    """Deepest row the camera passes while the sun is still above the dark threshold, that is a thin side card with
    an existing non-static loop (so 'still sliding'), not 3D [inf: Gary's 'towards the back' + 'still lit']."""
    best = None
    for r in rows:
        if r["pass_frame"] / tick > dark_s - 4.0 or is_static(r["mechanism"]):
            continue
        if all(r["sides"][s].get("mesh") and r["sides"][s]["thickness_cm"] <= MAX_THICKNESS_CM for s in SIDES):
            best = r
    return best


def still_plan(rows, keeper_guid, chain_guids):
    """Per P06 row: still (Static + PhaseOffsetCycles 0), keep (keeper), chain, or already_still.
    Refuses a row whose curves are not ~0 at phase 0 (it would hold a pose)."""
    plan, refusals = [], []
    for r in rows:
        g = r["cue_guid"]
        if g == keeper_guid:
            plan.append({"cue_guid": g, "label": r["label"], "action": "keep"})
        elif g in chain_guids:
            plan.append({"cue_guid": g, "label": r["label"], "action": "chain"})
        elif at_rest_now(r):
            plan.append({"cue_guid": g, "label": r["label"], "action": "already_still"})
        else:
            bad = {k: v for k, v in r.get("curve_at0", {}).items() if abs(float(v)) > FLAT_EPS}
            if bad or not r.get("curve_at0"):
                refusals.append("STILL_CURVE_NOT_ZERO_AT_PHASE0 %s %s" % (r["label"], bad or "curve_at0 missing"))
            plan.append({"cue_guid": g, "label": r["label"], "action": "still", "show_index": r["show_index"],
                         "set": {"playback_mode": "STATIC", "phase_offset_cycles": 0.0}})
    return plan, refusals


def _r(x, nd=3):
    return round(float(x), nd)


def inputs_for(meas, window=None, keeper_guid=None):
    """Everything the plan was computed from; APPLY recomputes it live and compares the hash. Every P06 row's
    mechanism hash is included, so any edit anywhere in P06 after DRY makes the plan stale."""
    out = {"passage_guid": meas["passage_guid"], "tick": _r(meas["tick"], 6), "keeper": keeper_guid,
           "all_rows": [[r["cue_guid"], r["mechanism_sha"]] for r in meas["rows"]],
           "law_points": [[int(f), _r(d)] for f, d in meas["law"]["points"]], "segment_end": int(meas["law"]["segment_end"]),
           "modulation": {k: meas["modulation"].get(k) for k in ("wing_modulation", "speed_shaped", "longitudinal_offset")}}
    if window is not None:
        by = {r["cue_guid"]: r for r in meas["rows"]}
        side = window["side"]
        out["side"] = side
        out["rows"] = []
        for g in window["cue_guids"]:
            r = by[g]
            s = r["sides"][side]
            out["rows"].append({"cue_guid": g, "show_index": r["show_index"], "label": r["label"],
                                "station_cm": _r(r["station_cm"]), "pass_frame": int(r["pass_frame"]),
                                "height_cm": _r(s["height_cm"]), "thickness_cm": _r(s["thickness_cm"]),
                                "hinge_route_cm": _r(s["hinge_route_cm"]), "has_top": bool(r["has_top"]),
                                "mesh": s["mesh"], "has_hinge_socket": bool(s["has_hinge_socket"]),
                                "lateral_min_cm": _r(s["lateral_min_cm"]), "lateral_max_cm": _r(s["lateral_max_cm"])})
        out["brace"] = window.get("brace")
    return out


def inputs_hash(inputs):
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# =====================================================================================================================
# Timing (PassFrame origin only -- no absolute Master frame is ever authored)
# =====================================================================================================================

def creak_for_slam(inputs, slam_s, final_impact_s):
    """Creak frame (relative to the segment start) that puts the chain's final impact at slam_s P06 seconds."""
    return (float(slam_s) - float(final_impact_s)) * float(inputs["tick"])


def creak_for_lead(inputs, lead_cm):
    law = {"points": [tuple(p) for p in inputs["law_points"]]}
    c = inputs["rows"][0]["hinge_route_cm"] - lead_cm
    require(c >= 0, "CREAK_BEFORE_SEGMENT_START: camera would need to be %.0f cm before the Passage start" % -c)
    return frame_at_distance(law, c)


def timing(inputs, solver_rows, t_end_s, creak, events=()):
    """PhaseOffsetCycles per row so that row k's phase is 0 at creak + start_k:
    Offset_k = ((PassFrame_k - creak)/tick - start_k) * rate_k  [PassageActor.cpp:1384-1424]."""
    law = {"points": [tuple(p) for p in inputs["law_points"]], "segment_end": inputs["segment_end"]}
    tick = float(inputs["tick"])
    rows = inputs["rows"]
    refusals, out = [], []
    if creak < 0:
        refusals.append("CREAK_BEFORE_SEGMENT_START: %.2f s" % (creak / tick))
    end = creak + t_end_s * tick
    if end > inputs["segment_end"]:
        refusals.append("FALL_PAST_SEGMENT_END: rest at %.0f > segment end %d (mechanisms freeze outside the Passage, "
                        "PassageActor.cpp:1272)" % (end, inputs["segment_end"]))
    for r, s in zip(rows, solver_rows):
        rate = float(s["CycleRateHz"])
        start_s = float(s["start_s"])
        out.append({"cue_guid": r["cue_guid"], "CycleRateHz": rate,
                    "PhaseOffsetCycles": ((r["pass_frame"] - creak) / tick - start_s) * rate, "start_s": start_s,
                    "duration_s": float(s["duration_s"]), "pass_frame_rel": r["pass_frame"],
                    "hinge_minus_station_cm": r["hinge_route_cm"] - r["station_cm"],
                    "camera_mps_at_hinge": speed_at_distance(law, r["hinge_route_cm"], tick)})
    imp = [e for e in events if e.get("type") in ("floor", "wall") and e.get("slab") == len(rows) - 1]
    first = [e for e in events if e.get("type") in ("floor", "wall")]
    cam = lambda f: distance_at_frame(law, f)
    res = {"creak_frame_rel": creak, "creak_s": creak / tick, "rest_s": end / tick,
           "segment_end_s": inputs["segment_end"] / tick, "camera_cm_at_creak": cam(max(creak, 0.0)),
           "lead_cm_at_creak": rows[0]["hinge_route_cm"] - cam(max(creak, 0.0)),
           "camera_mps_at_creak": speed_at_distance(law, cam(max(creak, 0.0)), tick), "rows": out,
           "refusals": refusals}
    for name, lst in (("first_impact", first), ("final_impact", imp)):
        if lst:
            f = creak + lst[0]["t"] * tick
            res[name + "_s"] = f / tick
            res[name + "_type"] = lst[0]["type"]
            res["camera_cm_at_" + name] = cam(f)
            res["row0_ahead_cm_at_" + name] = rows[0]["hinge_route_cm"] - cam(f)
            res["last_row_ahead_cm_at_" + name] = rows[-1]["hinge_route_cm"] - cam(f)
    return res


def phase_at(row_timing, frame_rel):
    """The C++ OneShot law for a row, PassFrame origin [decl PassageActor.cpp:1424-1431]."""
    tick = row_timing["_tick"]
    p = row_timing["PhaseOffsetCycles"] + (frame_rel - row_timing["pass_frame_rel"]) / tick * row_timing["CycleRateHz"]
    return min(1.0, max(0.0, p))


def daylight_at(timeline, t):
    """Linear interpolation of a p06_sunset_dry.json timeline [{t, daylight, elev}] (P06 seconds)."""
    if not timeline:
        return None
    pts = sorted((float(x["t"]), float(x["daylight"])) for x in timeline)
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, a), (t1, b) in zip(pts[:-1], pts[1:]):
        if t <= t1:
            return a + (b - a) * (t - t0) / (t1 - t0)
    return pts[-1][1]
