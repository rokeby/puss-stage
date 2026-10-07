"""P02 brighten second half: DRY / APPLY / REVERT. Raise dead practicals to a low glow and lift the TOP lights of the
P02 bays in the second half of the route (INTENSITY SET), and -- schema 2, 7 Oct -- make every SCORE lamp in those bays
strike earlier and stay lit behind the camera (DRAMA SET).

SCHEMA 2 (7 Oct, after APPLY 20261007-022814 had no measurable effect): the 6 Oct rig pattern keys P02 SCORE lamps with
Drama StrikeDistanceCm 650 / StrikeRampCm 150 / UnstruckIntensityScale 0 and AfterPass DECAY (B15-B17) or EXTINGUISH
(B18-B19) (p02_rig_pattern_record.json after_cue_rows, offline read 7 Oct). EvaluateStrike returns the unstruck level
until the camera is within StrikeDistanceCm and drops back to it after the pass for Extinguish/Decay
(InfinityStageLightDrama.cpp:23-57; declaration-proven from source); per the header the unstruck lamp is switched off,
not dimmed (InfinityStageLightDrama.h:30). So the camera sees at most ~6.5 m of lit lamps ahead; raising intensity
alone could not show. DRAMA SET (params "drama": true by default), for the SAME selected bays:
  * every enabled LIGHT row "P02 SCORE B## <look> <role>" (not *_BODY; minus params.drama_skip_roles, default none --
    so BEAM_R and LOW_SIDE_* ARE included) whose Drama.bStrikeOnApproach is true:
      lighting.drama.strike_distance_cm -> max(before, params.strike_distance_cm 2500)  (never shortened)
      lighting.drama.strike_ramp_cm     -> params.strike_ramp_cm 600
      lighting.drama.after_pass         -> params.after_pass_override "HOLD" when before is DECAY/EXTINGUISH (null = off)
    UnstruckIntensityScale, AfterPassDistanceCm, DecayDistanceCm, IgnitionStutter, bStrikeOnApproach are NEVER written.
  * a field already at its target is not written (no-op fields are not targets). Each (row, field) is one TARGET with
    its own before/after; plan.counts.targets counts FIELDS (intensity + drama), plan.counts.rows counts attachments.
Field names: FInfinityStageLightDrama bStrikeOnApproach/StrikeDistanceCm/StrikeRampCm/UnstruckIntensityScale/AfterPass
(InfinityStageLightDrama.h:39,44,49,61,65), enum EInfinityLightAfterPass Hold/Decay/Extinguish (:10-18), Lighting.Drama
(InfinityStageTypes.h:364) -- declaration-proven. Python names strike_distance_cm / strike_ramp_cm / after_pass and
unreal.InfinityLightAfterPass are measured by earlier live writers (lighting_looks_apply.py:1533-1551,
lighting_events_apply.py:970-986) and the plain-state reader (_infinity_attachment_state.py DRAMA_FIELDS).
ORDER while the schema-1 record of APPLY 20261007-022814 is active: REVERT (restores its 32 intensities; works on a
schema-1 record) -> DRY -> APPLY (both sets, expected_targets = the DRY's plan.counts.targets).

Gary, 7 Oct (P02, after the straighten + retime to 47.52 s): "Brighten second half". Earlier notes this honours:
dead bulbs must glow minimally (GARY_PIE_NOTES_2026-10-05.md:255), light the wings lurid "from above" / with the
practicals and NO light shooting through L to R (GARY_PIE_NOTES_2026-10-05.md:220-222) -- so BEAM_R and the LOW_SIDE
rows are never written. A live probe at the 60 % still (probe_p02_view.py) read B18-B19 practicals at 0.0 and
88-209 cd and B20-21 (P02_MYSTIC) TOP_L/TOP_R at 0.0.

INTENSITY SET (lighting.intensity of existing Show attachments; with the DRAMA SET above these four fields are all
this tool writes: no colour, cone, other drama field, transform, enabled; no row added or removed):
  * selection: P02 bays whose LIVE station distance / LIVE route length >= params.from_fraction (0.45); station
    distances from Structure 02's GatherStations, route length from the Passage actor's GetRouteLengthStatus.
  * practicals: enabled LIGHT rows "P02 SCORE B## <look> PRACTICAL..." (not *_BODY) with intensity < practical_floor
    (120) are raised to exactly practical_floor. The value is in the ROW's own units and the row must carry
    params.practical_units (LUMENS): P02 practicals are POINT lights in LUMENS, so the probe's "88-209" and the brief's
    "120 cd" are lumens (120 lm point ~ 9.5 cd); GAP bays' PRACTICAL_GLIMMER sits at 160 lm. Colour/temperature are
    kept (see COOL_COLOUR warnings). Rows in other units are refused per row (UNITS_MISMATCH, listed).
  * tops: enabled LIGHT rows "... TOP_L" / "... TOP_R" get max(before, min(top_max_cd, max(before*top_scale,
    top_floor_cd))) -- never lowered. Defaults top_scale 2.0, top_floor_cd 60, top_max_cd 200; rows must carry
    params.top_units (CANDELAS).
  * untouched and listed: disabled rows, rows already at/above the target, every other role, every row outside the
    selected bays, every non-SCORE row, args skip_labels.

GUARDS (APPLY): confirm "APPLY P02BRIGHTEN"; expected_targets (the DRY count) REQUIRED; optional expected_bays; no PIE,
no open Sequencer, no ZZ_ actors, clean census (rig pattern check_context); no active record; every foreign active
record that names a target GUID must be in ack_records (copy VERBATIM from the DRY report). Then: Backups/PreP02Brighten-
<run> (Show + level), exclusive fsynced record with every before value BEFORE the first write, write, scope check
(every row of every cue == before except exactly the targets' lighting.intensity; outside hash; export text with only
the targets' Intensity masked), materialize Passage 02 (+ Structure 02 refit), narrow save (Show + level only), read
back from the saved asset, record status saved_readback_verified. Any failure before save rolls back in memory.
REVERT: confirm "REVERT P02BRIGHTEN"; drift check (every target must still read its after value, all drifts listed);
writes the recorded before values, requires them bit-exact in memory, same scope/materialize/save/read-back chain,
archives the record as .reverted-<run>.

Proof tiers (AGENTS.md), per claim:
* declaration-proven: FInfinityCueAttachment field order AttachmentGuid .. RelativeTransform .. Lighting
  (Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:434, :461, :466);
  FInfinityStageLightSettings::Intensity is float, default 5000 (InfinityStageTypes.h:204), Color :207,
  IntensityUnits default Lumens (:201; enum :174-181);
  _set_pair_attachments writes the cue array with show.modify() (lighting_looks_apply.py:1292-1300); _save_narrow
  refuses any dirty package but SHOW_PATH + the level (lighting_looks_apply.py:1657-1676); _backup
  (lighting_looks_apply.py:1616-1633); _materialize_passage (lighting_scores_apply.py:2879-2896);
  scan_foreign_records skips terminal statuses (lighting_scores_apply.py:1966-1995); a lamp's route distance = its cue's
  wing DistanceCm + RelativeTransform.X (InfinityStagePassageActor.cpp:1651-1665, cited by p04_window_shadows.py:31).
* measured (by earlier live runs of the code reused here): the struct read/modify/write of an attachment lighting field
  (p03_atmos.py:1282-1306 _write_fields, APPLY report p03_atmos_report_APPLY_20261006-233515.json); GatherStations
  rows carry cue_guid + distance_cm (rig_lamp_drop.py:790-803, live on P02 5-6 Oct); GetRouteLengthStatus via the
  unwrap pattern (p02_straighten.py:512-514, live 7 Oct). Offline (files read 7 Oct): P02 rows in
  p02_rig_pattern_record.json after_cue_rows (saved_readback_verified 6 Oct 22:38) and lighting_scores_record_P02.json
  (B06/B22 GAP bays); P02 wing interval uniform (passage_slow_walk_P02_latest.json plan.intervals) and route
  11857.83 cm (p02_straighten_dry_P02STR-20261007-015527.json required_cm).
* inferred (the DRY confirms each; listed in the report "inferred"): station n at 250 + 500 (n-1) cm, so the 0.45 cut
  falls between B11 (0.443) and B12 (0.485) -- derived from the uniform intervals, not read from stations; the live
  intensities still equal the 6 Oct record values (hand edits after it would change before/after); the Intensity
  field appears 0 or 1 times inside each target's Lighting=(..) export group (masked by p01_rig_pattern._mask_intensity);
  that a raised struck-on-approach lamp (drama strike_on_approach true, unstruck_intensity_scale 0) reads as a glow once
  struck -- the editor intensity is the struck level, not what the camera sees before the strike.

Args (p02_brighten_args.json via p02_brighten_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P02BRIGHTEN", "params": {...DEFAULTS overrides},
   "expected_targets": null|int (= DRY plan.counts.targets, which counts FIELDS: intensity + drama), "expected_bays":
   null|[labels], "ack_records": [...], "allow_dirty": []}
  drama params: "drama" true, "strike_distance_cm" 2500, "strike_ramp_cm" 600, "after_pass_override" "HOLD"|null,
  "drama_skip_roles" [] (e.g. ["BEAM_R"]).
Markers: P02BRIGHTEN_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|...; any stop P02BRIGHTEN_STOPPED|run=<id>|<reason>.
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import math
import os
import re
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
RIG_PATTERN_PATH = os.path.join(HERE, "p01_rig_pattern.py")
RECORD_PATH = os.path.join(HERE, "p02_brighten_record.json")
MARK = "P02BRIGHTEN"
CONFIRM_TOKEN = "P02BRIGHTEN"
VALID_MODES = ("DRY", "APPLY", "REVERT")
PASSAGE = "P02"
BACKUP_STEM = "PreP02Brighten"
SCHEMA_VERSION = 2
FIELD = "lighting.intensity"
P_STRIKE = "lighting.drama.strike_distance_cm"
P_RAMP = "lighting.drama.strike_ramp_cm"
P_AFTER = "lighting.drama.after_pass"
PATHS = (FIELD, P_STRIKE, P_RAMP, P_AFTER)          # the ONLY fields this tool may write
ENUM_PATHS = (P_AFTER,)
AFTER_PASS_NAMES = ("HOLD", "DECAY", "EXTINGUISH")  # InfinityStageLightDrama.h:10-18
EXPORT_NAMES = {P_STRIKE: "StrikeDistanceCm", P_RAMP: "StrikeRampCm", P_AFTER: "AfterPass"}  # inside Drama=(..)
UNIT_NAMES = ("UNITLESS", "CANDELAS", "LUMENS", "EV", "NITS")   # InfinityStageTypes.h:174-181
SCORE_RE = re.compile(r"^P02 SCORE B(\d{2}) (\S+) (\S+)$")
DEFAULTS = {
    "from_fraction": 0.45,          # Gary: "second half"; 0.45 starts just before the midpoint (brief, 7 Oct)
    "practical_floor": 120.0,       # dead / dim practicals raised to exactly this, in practical_units
    "practical_units": "LUMENS",    # P02 practicals are POINT lights in LUMENS (p02_rig_pattern_record.json, 7 Oct)
    "top_units": "CANDELAS",        # P02 TOP_L/TOP_R are SPOT lights in CANDELAS (same record)
    "top_scale": 2.0,
    "top_floor_cd": 60.0,
    "top_max_cd": 200.0,
    "practical_role_re": r"^PRACTICAL(_[A-Z]+)*$",
    "top_roles": ["TOP_L", "TOP_R"],
    "skip_labels": [],
    # DRAMA SET (schema 2)
    "drama": True,
    "strike_distance_cm": 2500.0,   # never shortens a longer strike
    "strike_ramp_cm": 600.0,
    "after_pass_override": "HOLD",  # DECAY/EXTINGUISH -> HOLD; null leaves AfterPass alone
    "drama_skip_roles": [],         # e.g. ["BEAM_R"] to keep a role's keying as it is
}
PARAM_RANGES = {"from_fraction": (0.0, 0.99), "practical_floor": (1.0, 1000.0), "top_scale": (1.0, 4.0),
                "top_floor_cd": (0.0, 500.0), "top_max_cd": (1.0, 1000.0),
                "strike_distance_cm": (0.0, 6000.0), "strike_ramp_cm": (1.0, 3000.0)}
REL_TOL = 1.0e-6
INFERRED = [
    "station n at 250 + 500 (n-1) cm (uniform intervals, passage_slow_walk_P02_latest.json) -> cut between B11/B12",
    "live intensities still equal the 6 Oct record values (p02_rig_pattern_record.json after_cue_rows)",
    "Intensity appears 0/1 times inside each target's Lighting=(..) export group",
    "a raised strike-on-approach lamp (unstruck_intensity_scale 0) only glows once struck",
    "materialize carries the new Show intensity to the spawned light (not read back from components here)",
    "ExportText nests Drama as Drama=(..) inside Lighting=(..) and omits default-valued fields (HOLD, 2500 are "
    "defaults); a missing Drama group refuses EXPORT_NO_DRAMA, so the DRY proves or refutes it",
    "with strike 2500 + HOLD the second-half lamps read as lit from ~25 m ahead and stay lit behind; not rendered here",
]


class P02BrightenError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise P02BrightenError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def _short(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "%.4g" % value
    return _enum_name(value)


def report_path(mode, run, folder=None):
    return os.path.join(folder or HERE, "p02_brighten_report_%s_%s.json" % (mode, run))


# --------------------------------------------------------------------------
# p01_rig_pattern.py reused by import (never edited, never its main()): same loader shape as p03_atmos.py:827-866.
# --------------------------------------------------------------------------
def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else inner + "." + node.attr
    return None


def _is_main_guard(node):
    return (isinstance(node, ast.If) and not node.orelse and len(node.body) == 1
            and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "unreal" and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main")


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1]) and sum(1 for n in tree.body if _is_main_guard(n)) == 1,
            "MAIN_GUARD_SHAPE|" + path)
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


RIG_PATTERN_API = ("load_modules", "passage_config", "load_aims", "_runtime_plain", "_all_rows", "_ctx_facts",
                   "check_context", "_materialize", "_export_texts", "_mask_intensity", "f32")


def load_rig_pattern():
    rp = load_without_main(RIG_PATTERN_PATH, "_p01_rig_pattern_for_p02_brighten")
    missing = [n for n in RIG_PATTERN_API if not callable(getattr(rp, n, None))]
    missing += [n for n in ("_OWN_GUID", "FORBIDDEN_TARGET_LABEL") if not hasattr(rp, n)]
    require(not missing, "RIG_PATTERN_API_DRIFT|" + ",".join(missing))
    return rp


# --------------------------------------------------------------------------
# Args.
# --------------------------------------------------------------------------
def _finite(value, label):
    require(not isinstance(value, bool), "%s_NOT_NUMBER|%r" % (label, value))
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|%r" % (label, value))
    return number


def check_params(raw):
    raw = dict(raw or {})
    unknown = sorted(set(raw) - set(DEFAULTS))
    require(not unknown, "PARAMS_UNKNOWN|%s" % unknown)
    p = copy.deepcopy(DEFAULTS)
    p.update(copy.deepcopy(raw))
    for key, (lo, hi) in PARAM_RANGES.items():
        p[key] = _finite(p[key], "PARAM_" + key.upper())
        require(lo <= p[key] <= hi, "PARAM_RANGE|%s=%s|[%s,%s]" % (key, p[key], lo, hi))
    require(p["top_floor_cd"] <= p["top_max_cd"], "PARAM_TOP_FLOOR_ABOVE_MAX|%s>%s" % (p["top_floor_cd"], p["top_max_cd"]))
    try:
        rx = re.compile(p["practical_role_re"])
    except (re.error, TypeError) as error:
        raise P02BrightenError("PARAM_PRACTICAL_ROLE_RE|%s" % error)
    require(not rx.match("TOP_L") and not rx.match("BEAM_R") and not rx.match("LOW_SIDE_L_KEY"),
            "PARAM_PRACTICAL_ROLE_RE_TOO_WIDE|%s" % p["practical_role_re"])
    for key in ("practical_units", "top_units"):
        require(p[key] in UNIT_NAMES, "PARAM_UNITS|%s=%r" % (key, p[key]))
    tops = p["top_roles"]
    require(isinstance(tops, list) and tops and all(r in ("TOP_L", "TOP_R") for r in tops)
            and len(set(tops)) == len(tops), "PARAM_TOP_ROLES|%r (TOP_L/TOP_R only)" % (tops,))
    skip = p["skip_labels"]
    require(isinstance(skip, list) and all(isinstance(s, str) and s for s in skip), "PARAM_SKIP_LABELS|%r" % (skip,))
    require(isinstance(p["drama"], bool), "PARAM_DRAMA_NOT_BOOL|%r" % (p["drama"],))
    ov = p["after_pass_override"]
    require(ov is None or ov == "HOLD", "PARAM_AFTER_PASS_OVERRIDE|%r (HOLD or null only)" % (ov,))
    dskip = p["drama_skip_roles"]
    require(isinstance(dskip, list) and all(isinstance(s, str) and s for s in dskip),
            "PARAM_DRAMA_SKIP_ROLES|%r" % (dskip,))
    return p


def check_args(args):
    args = dict(args or {})
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(args.get("confirm") == "%s %s" % (mode, CONFIRM_TOKEN),
                "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, CONFIRM_TOKEN))
    expected = args.get("expected_targets")
    require(expected is None or (isinstance(expected, int) and not isinstance(expected, bool) and expected > 0),
            "EXPECTED_TARGETS_INVALID|%r" % (expected,))
    if mode == "APPLY":
        require(expected is not None, "EXPECTED_TARGETS_REQUIRED|copy plan.counts.targets from the DRY report")
    bays = args.get("expected_bays")
    require(bays is None or (isinstance(bays, list) and all(isinstance(b, str) for b in bays)),
            "EXPECTED_BAYS_INVALID|%r" % (bays,))
    acks = list(args.get("ack_records", []) or [])
    require(all(isinstance(a, str) for a in acks), "ACK_RECORDS_INVALID")
    return {"mode": mode, "confirm": args.get("confirm"), "params": check_params(args.get("params")),
            "expected_targets": expected, "expected_bays": None if bays is None else list(bays),
            "ack_records": acks, "allow_dirty": list(args.get("allow_dirty", []) or [])}


# --------------------------------------------------------------------------
# Plan (pure).
# --------------------------------------------------------------------------
def f32(value):
    import struct
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def close(a, b, tol=REL_TOL):
    a, b = float(a), float(b)
    return abs(a - b) <= tol * max(abs(a), abs(b), 1.0e-3)


def bay_fractions(plain, stations, route_length_cm):
    """Per P02 bay: its station distance and route fraction (station distance / route length)."""
    route = _finite(route_length_cm, "ROUTE_LENGTH")
    require(route > 0.0, "ROUTE_LENGTH_NOT_POSITIVE|%s" % route)
    by_cue = {c["guid"]: c for c in plain["cues"]}
    missing = [g for g in plain["bay_guids"] if g not in by_cue]
    require(not missing, "BAY_GUID_UNRESOLVED|%s" % missing)
    dist = {}
    for s in stations:
        dist.setdefault(s["cue_guid"], []).append(_finite(s["distance_cm"], "STATION_DISTANCE"))
    out = []
    for g in plain["bay_guids"]:
        cue = by_cue[g]
        require(str(cue["label"]).startswith(PASSAGE + " "), "BAY_NOT_%s|%s" % (PASSAGE, cue["label"]))
        hits = dist.get(g, [])
        require(len(hits) == 1, "STATION_COUNT|cue=%s|count=%d" % (cue["label"], len(hits)))
        d = hits[0]
        require(-1.0 <= d <= route + 1.0, "STATION_OUTSIDE_ROUTE|cue=%s|d=%s|route=%s" % (cue["label"], d, route))
        tokens = sorted({m.group(1) for m in (SCORE_RE.match(str(r["label"])) for r in cue["attachments"]) if m})
        require(len(tokens) <= 1, "MIXED_BAY_TOKENS|cue=%s|%s" % (cue["label"], tokens))
        out.append({"cue_guid": g, "cue_label": cue["label"], "show_index": cue["show_index"],
                    "bay_token": tokens[0] if tokens else None, "distance_cm": d, "fraction": d / route})
    out.sort(key=lambda b: (b["distance_cm"], b["show_index"]))
    return out


def _target(cue, bay, row, index, role, look, kind, before, after):
    return {"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue["show_index"],
            "bay_token": bay["bay_token"], "fraction": bay["fraction"], "attachment_guid": row["guid"],
            "attachment_label": row["label"], "attachment_index": index, "role": role, "look": look,
            "kind": kind, "path": FIELD, "before": before, "after": after,
            "color": list(row["lighting"].get("color") or []),
            "temperature_kelvin": row["lighting"].get("temperature_kelvin")}


def build_plan(plain, stations, route_length_cm, params, forbidden=None):
    p = params
    practical_rx = re.compile(p["practical_role_re"])
    skip = set(p["skip_labels"])
    bays = bay_fractions(plain, stations, route_length_cm)
    for b in bays:
        b["selected"] = b["fraction"] >= p["from_fraction"]
    selected = [b for b in bays if b["selected"]]
    require(selected, "NO_BAYS_SELECTED|from_fraction=%s" % p["from_fraction"])
    by_cue = {c["guid"]: c for c in plain["cues"]}
    all_guids = [r["guid"] for c in plain["cues"] for r in c["attachments"]]
    targets, untouched, warnings, drama_untouched = [], [], [], []
    for bay in selected:
        cue = by_cue[bay["cue_guid"]]
        has_top = False
        for index, row in enumerate(cue["attachments"]):
            m = SCORE_RE.match(str(row["label"]))
            if not m:
                continue
            look, role = m.group(2), m.group(3)
            if role.endswith("_BODY"):
                continue
            is_practical = bool(practical_rx.match(role))
            is_top = role in p["top_roles"]
            has_top = has_top or is_top
            why = None
            if not (is_practical or is_top):
                why = "ROLE_NOT_IN_SCOPE"
            elif _enum_name(row["kind"]) != "LIGHT":
                why = "NOT_A_LIGHT"
            elif row["label"] in skip:
                why = "SKIP_LABEL"
            elif forbidden is not None and forbidden.search(str(row["label"])):
                why = "FORBIDDEN_LABEL"
            elif not row.get("enabled", True):
                why = "DISABLED"
            elif _enum_name(row["lighting"].get("intensity_units")) != (p["practical_units"] if is_practical
                                                                        else p["top_units"]):
                why = "UNITS_MISMATCH"
            if why is None:
                before = _finite(row["lighting"]["intensity"], "INTENSITY_BEFORE")
                require(before >= 0.0, "INTENSITY_NEGATIVE|%s|%s" % (row["label"], before))
                if is_practical:
                    after = f32(p["practical_floor"]) if before < p["practical_floor"] else before
                    kind = "practical"
                else:
                    after = f32(max(before, min(p["top_max_cd"], max(before * p["top_scale"], p["top_floor_cd"]))))
                    kind = "top"
                if after <= before:
                    why = "AT_OR_ABOVE_TARGET"
            if why is not None:
                if why != "ROLE_NOT_IN_SCOPE":
                    untouched.append({"cue_label": cue["label"], "label": row["label"], "role": role, "why": why,
                                      "intensity": row["lighting"].get("intensity")})
                if why == "UNITS_MISMATCH":
                    warnings.append("UNITS_MISMATCH|%s|%s" % (row["label"], row["lighting"].get("intensity_units")))
                continue
            require(all_guids.count(row["guid"]) == 1, "TARGET_GUID_NOT_UNIQUE|" + row["guid"])
            t = _target(cue, bay, row, index, role, look, kind, before, after)
            targets.append(t)
            rgb = t["color"][:3]
            if kind == "practical" and len(rgb) == 3 and rgb[2] > rgb[0]:
                warnings.append("COOL_COLOUR|%s|rgb=%s|K=%s (kept; Gary asked orange/white/pink for dead bulbs)"
                                % (row["label"], [round(c, 2) for c in rgb], t["temperature_kelvin"]))
            drama = row["lighting"].get("drama") or {}
            if drama.get("strike_on_approach") and float(drama.get("unstruck_intensity_scale", 1.0)) == 0.0:
                t["struck_only"] = True
        if not has_top:
            warnings.append("BAY_HAS_NO_TOP_ROWS|%s|B%s (only practicals can brighten it)"
                            % (cue["label"], bay["bay_token"]))
        if p["drama"]:
            _plan_drama(cue, bay, p, skip, forbidden, all_guids, targets, drama_untouched)
    require(targets, "ZERO_TARGETS")
    order = {path: i for i, path in enumerate(PATHS)}
    targets.sort(key=lambda t: (t["show_index"], t["attachment_index"], order[t["path"]]))
    keys = [(t["attachment_guid"], t["path"]) for t in targets]
    require(len(keys) == len(set(keys)), "TARGET_FIELD_DUPLICATE")
    inten = [t for t in targets if t["path"] == FIELD]
    drama = [t for t in targets if t["path"] != FIELD]
    counts = {"targets": len(targets), "intensity_rows": len(inten),
              "practical": sum(1 for t in inten if t["kind"] == "practical"),
              "top": sum(1 for t in inten if t["kind"] == "top"),
              "drama_rows": len({t["attachment_guid"] for t in drama}), "drama_fields": len(drama),
              "strike_fields": sum(1 for t in drama if t["path"] == P_STRIKE),
              "ramp_fields": sum(1 for t in drama if t["path"] == P_RAMP),
              "after_pass_fields": sum(1 for t in drama if t["path"] == P_AFTER),
              "rows": len({t["attachment_guid"] for t in targets}),
              "bays_selected": len(selected), "bays_total": len(bays), "untouched_listed": len(untouched),
              "drama_untouched_listed": len(drama_untouched),
              "struck_only": sum(1 for t in inten if t.get("struck_only"))}
    return {"passage": PASSAGE, "schema_version": SCHEMA_VERSION, "params": copy.deepcopy(p),
            "route_length_cm": float(route_length_cm),
            "bays": bays, "selected_bays": [b["cue_label"] for b in selected],
            "first_selected": {k: selected[0][k] for k in ("cue_label", "bay_token", "distance_cm", "fraction")},
            "targets": targets, "untouched": untouched, "drama_untouched": drama_untouched,
            "warnings": warnings, "counts": counts,
            "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
            "target_attachment_guids": sorted({t["attachment_guid"] for t in targets}),
            "inferred": list(INFERRED)}


def _plan_drama(cue, bay, p, skip, forbidden, all_guids, targets, untouched):
    """DRAMA SET for one selected bay: strike distance / ramp / after-pass of every enabled SCORE light that strikes."""
    dskip = set(p["drama_skip_roles"])
    for index, row in enumerate(cue["attachments"]):
        m = SCORE_RE.match(str(row["label"]))
        if not m:
            continue
        look, role = m.group(2), m.group(3)
        if role.endswith("_BODY"):
            continue
        drama = (row.get("lighting") or {}).get("drama") or {}
        why = None
        if _enum_name(row["kind"]) != "LIGHT":
            why = "NOT_A_LIGHT"
        elif role in dskip:
            why = "DRAMA_SKIP_ROLE"
        elif row["label"] in skip:
            why = "SKIP_LABEL"
        elif forbidden is not None and forbidden.search(str(row["label"])):
            why = "FORBIDDEN_LABEL"
        elif not row.get("enabled", True):
            why = "DISABLED"
        elif not drama.get("strike_on_approach"):
            why = "NOT_STRIKE_ON_APPROACH"
        fields = []
        if why is None:
            s0 = _finite(drama["strike_distance_cm"], "STRIKE_BEFORE")
            r0 = _finite(drama["strike_ramp_cm"], "RAMP_BEFORE")
            a0 = drama["after_pass"]
            a0n = _enum_name(a0)
            require(a0n in AFTER_PASS_NAMES, "AFTER_PASS_UNKNOWN|%s|%r" % (row["label"], a0))
            s1 = max(s0, float(p["strike_distance_cm"]))
            if s1 != s0:
                fields.append((P_STRIKE, s0, s1))
            if float(p["strike_ramp_cm"]) != r0:
                fields.append((P_RAMP, r0, float(p["strike_ramp_cm"])))
            ov = p["after_pass_override"]
            if ov is not None and a0n in ("DECAY", "EXTINGUISH") and a0n != ov:
                fields.append((P_AFTER, a0, ov))
            if not fields:
                why = "DRAMA_AT_TARGET"
        if why is not None:
            untouched.append({"cue_label": cue["label"], "label": row["label"], "role": role, "why": why})
            continue
        require(all_guids.count(row["guid"]) == 1, "TARGET_GUID_NOT_UNIQUE|" + row["guid"])
        for path, before, after in fields:
            t = _target(cue, bay, row, index, role, look, "drama", before, after)
            t["path"] = path
            t["unstruck_intensity_scale"] = drama.get("unstruck_intensity_scale")
            targets.append(t)


def check_expected(plan, expected_targets, expected_bays):
    if expected_targets is not None:
        require(plan["counts"]["targets"] == expected_targets,
                "EXPECTED_TARGETS|expected=%s|planned=%d" % (expected_targets, plan["counts"]["targets"]))
    if expected_bays is not None:
        require(sorted(expected_bays) == sorted(plan["selected_bays"]),
                "EXPECTED_BAYS|expected=%s|planned=%s" % (sorted(expected_bays), sorted(plan["selected_bays"])))


# --------------------------------------------------------------------------
# Rows model, scope, drift (pure) -- modelled on p03_atmos.py:596-652, single field lighting.intensity.
# --------------------------------------------------------------------------
def _row(all_rows, t):
    hits = [r for r in all_rows.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
    require(len(hits) == 1, "TARGET_ROW_RESOLVE|%s|count=%d" % (t["attachment_guid"], len(hits)))
    return hits[0]


def _path_of(t):
    path = t.get("path", FIELD)                      # schema-1 records carry path lighting.intensity
    require(path in PATHS, "TARGET_PATH_NOT_ALLOWED|%r" % (path,))
    return path


def _container(row, path):
    """(dict, key) holding the field at path inside a plain row."""
    parts = path.split(".")
    node = row
    for part in parts[:-1]:
        require(isinstance(node, dict) and part in node, "ROW_PATH_MISSING|%s" % path)
        node = node[part]
    require(isinstance(node, dict) and parts[-1] in node, "ROW_PATH_MISSING|%s" % path)
    return node, parts[-1]


def get_field(row, path):
    node, key = _container(row, path)
    return node[key]


def set_field(row, path, value):
    node, key = _container(row, path)
    node[key] = value


def same_value(path, a, b):
    """Enums compare by member name (plain reads '<InfinityLightAfterPass.HOLD: 0>', plans write 'HOLD')."""
    if path in ENUM_PATHS:
        return _enum_name(a) == _enum_name(b)
    return close(a, b)


def exact_value(path, a, b):
    if path in ENUM_PATHS:
        return _enum_name(a) == _enum_name(b)
    return float(a) == float(b)


def apply_rows(all_rows, targets, side):
    require(side in ("before", "after"), "SIDE_INVALID|%s" % side)
    out = copy.deepcopy(all_rows)
    for t in targets:
        set_field(_row(out, t), _path_of(t), t[side])
    return out


def scope_problems(base_all, live_all, targets, side, diff):
    """[] iff live == base with exactly the targets' (row, field) at their side value; every other field of every row
    of every cue unchanged."""
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    want_all = apply_rows(base_all, targets, side)
    written = {}
    for t in targets:
        written.setdefault(t["attachment_guid"], []).append(_path_of(t))
    problems = []
    for cue_guid in sorted(base_all):
        want, got = want_all[cue_guid], live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in got]:
            problems.append({"cue": cue_guid, "problem": "ROW_SET_OR_ORDER_CHANGED"})
            continue
        for w, g in zip(want, got):
            w2, g2 = copy.deepcopy(w), copy.deepcopy(g)
            for path in written.get(w["guid"], []):
                wv, gv = get_field(w2, path), get_field(g2, path)
                if not same_value(path, gv, wv):
                    problems.append({"cue": cue_guid, "guid": w["guid"], "path": path, "want": wv, "got": gv})
                set_field(w2, path, None)
                set_field(g2, path, None)
            d = diff(w2, g2)
            if d:
                problems.append({"cue": cue_guid, "guid": w["guid"], "label": w["label"], "differences": d})
    return problems


def field_drifts(all_rows, targets, side="after"):
    """Every target field whose live value != its side value (all of them, not the first)."""
    out = []
    for t in targets:
        hits = [r for r in all_rows.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
        if len(hits) != 1:
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "path": _path_of(t),
                        "live": "count=%d" % len(hits)})
            continue
        live = get_field(hits[0], _path_of(t))
        if not same_value(_path_of(t), live, t[side]):
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "path": _path_of(t),
                        "record": t[side], "live": live})
    return out


def exact_problems(all_rows, targets, side):
    """Bit-exact check (REVERT restores the recorded float32/double exactly; enums by member name)."""
    out = []
    for t in targets:
        got = get_field(_row(all_rows, t), _path_of(t))
        if not exact_value(_path_of(t), got, t[side]):
            out.append({"label": t["attachment_label"], "path": _path_of(t), "want": t[side], "got": got})
    return out


def check_record(record):
    require(record.get("passage") == PASSAGE and (record.get("plan") or {}).get("passage") == PASSAGE,
            "RECORD_PASSAGE_MISMATCH|%s" % record.get("passage"))
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|%s" % record.get("status"))
    require(record["plan"].get("targets"), "RECORD_NO_TARGETS")
    require(record.get("schema_version") in (1, SCHEMA_VERSION), "RECORD_SCHEMA|%r" % record.get("schema_version"))
    for t in record["plan"]["targets"]:
        _path_of(t)
        require("before" in t and "after" in t, "RECORD_TARGET_NO_ORIGINAL|%s" % t.get("attachment_label"))
        if _path_of(t) in ENUM_PATHS:
            require(_enum_name(t["before"]) in AFTER_PASS_NAMES and _enum_name(t["after"]) in AFTER_PASS_NAMES,
                    "RECORD_ENUM|%s" % t.get("attachment_label"))


# --------------------------------------------------------------------------
# Export text scope: mask only the targets' Intensity inside their Lighting=(..) group.
# --------------------------------------------------------------------------
_LIGHTING_OPEN = re.compile(r"(?<![A-Za-z])Lighting=\(")
_DRAMA_OPEN = re.compile(r"(?<![A-Za-z])Drama=\(")


def _close_paren(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise P02BrightenError("EXPORT_UNBALANCED")


def _top_level_items(inner):
    items, depth, start = [], 0, 0
    for i, ch in enumerate(inner):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(inner[start:i])
            start = i + 1
    items.append(inner[start:])
    return [x for x in items if x != ""]


def mask_drama(segment, guid, names):
    """Remove the top-level <name>=.. items of the Drama=(..) group that sits at the top level of the segment's first
    Lighting=(..) group. Items are split and re-joined, so a field omitted at its default (AfterPass=Hold,
    StrikeDistanceCm=2500) and a field present normalise to the same text wherever it sat in the group."""
    found = list(_LIGHTING_OPEN.finditer(segment))
    require(found, "EXPORT_NO_LIGHTING|guid=" + guid)
    l_open = found[0].end() - 1
    l_close = _close_paren(segment, l_open)
    inner = segment[l_open + 1:l_close]
    drama = [m for m in _DRAMA_OPEN.finditer(inner) if inner[:m.start()].count("(") == inner[:m.start()].count(")")]
    require(len(drama) == 1, "EXPORT_NO_DRAMA|guid=%s|count=%d" % (guid, len(drama)))
    d_open = drama[0].end() - 1
    d_close = _close_paren(inner, d_open)
    items = _top_level_items(inner[d_open + 1:d_close])
    kept = []
    for name in names:
        n = sum(1 for x in items if x.split("=", 1)[0] == name)
        require(n <= 1, "EXPORT_%s_COUNT|guid=%s|count=%d" % (name.upper(), guid, n))
    for item in items:
        if item.split("=", 1)[0] not in names:
            kept.append(item)
    new_inner = inner[:d_open + 1] + ",".join(kept) + inner[d_close:]
    return segment[:l_open + 1] + new_inner + segment[l_close:]


def _paths_by_guid(targets):
    out = {}
    for t in targets:
        out.setdefault(t["attachment_guid"].upper(), set()).add(_path_of(t))
    return out


def normalize_export(rp, texts, targets):
    """Mask exactly each target's written fields: Lighting.Intensity (rp._mask_intensity, as schema 1) and
    Lighting.Drama.StrikeDistanceCm/StrikeRampCm/AfterPass (mask_drama). Everything else stays in the hash."""
    paths = _paths_by_guid(targets)
    seen = {g: 0 for g in paths}
    out = []
    for text in texts:
        marks = list(rp._OWN_GUID.finditer(text))
        pieces, cursor = [], 0
        for index, match in enumerate(marks):
            guid = match.group(1).upper()
            if guid not in paths:
                continue
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            pieces.append(text[cursor:match.start()])
            segment = text[match.start():end]
            if FIELD in paths[guid]:
                segment = rp._mask_intensity(segment, guid, "Intensity")
            names = [EXPORT_NAMES[p] for p in PATHS if p in paths[guid] and p in EXPORT_NAMES]
            if names:
                segment = mask_drama(segment, guid, names)
            pieces.append(segment)
            cursor = end
            seen[guid] += 1
        pieces.append(text[cursor:])
        out.append("".join(pieces))
    require(all(c == 1 for c in seen.values()), "EXPORT_TARGET_COUNT|%s" % _canonical({g: c for g, c in seen.items()
                                                                                       if c != 1}))
    return out


def export_hash(rp, texts, targets):
    return _sha256_text("\n".join(normalize_export(rp, texts, targets)))


def unacked_records(foreign, acks):
    return sorted({h["path"] for h in foreign} - set(acks))


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a module global.
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _unwrap(res):
    """(bool ok, value...) / value -> value or None (p02_straighten.py unwrap_tuple)."""
    if isinstance(res, tuple):
        if res and isinstance(res[0], bool):
            if not res[0]:
                return None
            res = res[1:]
        return res[0] if len(res) == 1 else res
    return res


def _find_structure(show, cfg):
    """rig_lamp_drop.py:776-788."""
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in subsystem.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStageStructureActor"
             and a.get_actor_label() == cfg["structure_label"]]
    require(len(found) == 1, "STRUCTURE_COUNT|label=%s|count=%d" % (cfg["structure_label"], len(found)))
    passage = found[0].get_editor_property("passage")
    require(passage is not None and passage.get_actor_label().startswith(cfg["actor_prefix"]),
            "STRUCTURE_PASSAGE_WRONG|" + cfg["key"])
    require(passage.get_editor_property("show_asset") == show, "STRUCTURE_SHOW_WRONG")
    return found[0], passage


def _stations(tool, structure):
    """rig_lamp_drop.py:790-803 (C++ GatherStations)."""
    result = structure.gather_stations()
    if isinstance(result, tuple) and len(result) == 3:
        ok, stations, error = result
        require(bool(ok), "GATHER_STATIONS_FAILED|" + str(error))
    elif isinstance(result, tuple) and len(result) == 2:
        stations, error = result
    else:
        stations, error = result, ""
    require(stations is not None and len(list(stations)) > 0, "GATHER_STATIONS_EMPTY|" + str(error))
    return [{"cue_guid": tool._guid_text(s.get_editor_property("cue_guid")),
             "distance_cm": float(s.get_editor_property("distance_cm"))} for s in stations]


def _route_length(passage):
    """p02_straighten.py:512-514: GetRouteLengthStatus -> (required TotalDistanceCm, ...)."""
    res = _unwrap(passage.get_route_length_status())
    if isinstance(res, tuple):
        res = res[0]
    require(res is not None, "ROUTE_LENGTH_UNREADABLE")
    spline = float(passage.get_editor_property("route").get_spline_length())
    return float(res), spline


def _enum_member(enum_type, name):
    """lighting_events_apply.py:770-774."""
    for candidate in (name, name.upper(), name.title().replace("_", "")):
        if hasattr(enum_type, candidate):
            return getattr(enum_type, candidate)
    raise P02BrightenError("ENUM_MEMBER_MISSING|enum=%s|name=%s" % (enum_type, name))


def _live_field(lighting, drama, path):
    if path == FIELD:
        return float(lighting.get_editor_property("intensity"))
    if path == P_STRIKE:
        return float(drama.get_editor_property("strike_distance_cm"))
    if path == P_RAMP:
        return float(drama.get_editor_property("strike_ramp_cm"))
    require(path == P_AFTER, "TARGET_PATH_NOT_ALLOWED|" + path)
    return str(drama.get_editor_property("after_pass"))


def _write_fields(tool, show, targets, side, check_side=None):
    """p03_atmos.py:1282-1306 (_write_fields) for the four PATHS. Drama is a nested struct copy: read it, set the
    fields, set it back on the lighting copy, set lighting back on the attachment (lighting_looks_apply.py:1531-1552)."""
    cues = list(show.get_editor_property("cues"))
    by_cue = {}
    for t in targets:
        by_cue.setdefault(t["cue_guid"], []).append(t)
    for cue_guid, items in sorted(by_cue.items()):
        matches = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
        require(len(matches) == 1 and matches[0] == items[0]["show_index"], "TARGET_CUE_RESOLVE|" + cue_guid)
        index = matches[0]
        require(str(cues[index].get_editor_property("label")) == items[0]["cue_label"], "TARGET_LABEL_DRIFT|" + cue_guid)
        attachments = tool._pair_attachments(cues[index])
        by_row = {}
        for t in items:
            by_row.setdefault(t["attachment_guid"], []).append(t)
        for row_guid, row_targets in sorted(by_row.items()):
            hits = [a for a in attachments if tool._guid_text(a.get_editor_property("attachment_guid")) == row_guid]
            require(len(hits) == 1, "TARGET_ATTACHMENT_RESOLVE|" + row_guid)
            attachment = hits[0]
            require(str(attachment.get_editor_property("label")) == row_targets[0]["attachment_label"],
                    "TARGET_ATTACHMENT_LABEL_DRIFT|" + row_guid)
            lighting = attachment.get_editor_property("lighting")
            drama = lighting.get_editor_property("drama")
            touched_drama = False
            for t in row_targets:
                path = _path_of(t)
                if check_side is not None:
                    live = _live_field(lighting, drama, path)
                    require(same_value(path, live, t[check_side]), "TARGET_FIELD_DRIFT|%s|%s|live=%r|want=%r"
                            % (t["attachment_label"], path, live, t[check_side]))
                if path == FIELD:
                    lighting.set_editor_property("intensity", float(t[side]))
                elif path == P_STRIKE:
                    drama.set_editor_property("strike_distance_cm", float(t[side]))
                    touched_drama = True
                elif path == P_RAMP:
                    drama.set_editor_property("strike_ramp_cm", float(t[side]))
                    touched_drama = True
                else:
                    name = _enum_name(t[side])
                    require(name in AFTER_PASS_NAMES, "AFTER_PASS_UNKNOWN|%r" % (t[side],))
                    drama.set_editor_property("after_pass", _enum_member(unreal.InfinityLightAfterPass, name))
                    touched_drama = True
            if touched_drama:
                lighting.set_editor_property("drama", drama)
            attachment.set_editor_property("lighting", lighting)
        tool._set_pair_attachments(show, index, attachments)


def _gather(rp, tool, cfg):
    aims, record_passage_guid = rp.load_aims(cfg["scores_record"])
    show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    require(show is not None, "SHOW_ASSET_MISSING")
    plain = rp._runtime_plain(tool, show, record_passage_guid, cfg)
    structure, passage = _find_structure(show, cfg)
    require(tool._guid_text(passage.get_editor_property("passage_guid")) == plain["passage_guid"],
            "PASSAGE_GUID_MISMATCH")
    stations = _stations(tool, structure)
    route, spline = _route_length(passage)
    return {"show": show, "plain": plain, "stations": stations, "route_length_cm": route, "spline_length_cm": spline,
            "record_passage_guid": record_passage_guid}


def _plain_again(rp, tool, show, g, cfg):
    return rp._all_rows(rp._runtime_plain(tool, show, g["record_passage_guid"], cfg))


def _scan_foreign(scores, guids):
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, guids, exclude=[RECORD_PATH])


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False, "inferred": INFERRED}
    tool = None
    try:
        rp = load_rig_pattern()
        scores, tool = rp.load_modules()
        cfg = rp.passage_config(PASSAGE)
        report["sources"] = {"rig_pattern_sha256": rp.SOURCE_SHA256, "scores_sha256": scores.SOURCE_SHA256}
        ctx = rp._ctx_facts(tool)
        report["context"] = ctx
        rp.check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        g = _gather(rp, tool, cfg)
        show = g["show"]
        before_all = rp._all_rows(g["plain"])
        diff = tool._state_differences

        if mode == "REVERT":
            return _revert(args, run, report, rp, scores, tool, cfg, g, before_all)

        plan = build_plan(g["plain"], g["stations"], g["route_length_cm"], args["params"], rp.FORBIDDEN_TARGET_LABEL)
        problems = scope_problems(before_all, apply_rows(before_all, plan["targets"], "after"), plan["targets"],
                                  "after", diff)
        require(not problems, "MODEL_SELF_CHECK|%s" % _canonical(problems)[:2000])
        texts_hash = export_hash(rp, rp._export_texts(show), plan["targets"])
        foreign = _scan_foreign(scores, plan["target_attachment_guids"])
        unacked = unacked_records(foreign, args["ack_records"])
        report.update({"plan": plan, "passage_guid": g["plain"]["passage_guid"],
                       "route_length_cm": g["route_length_cm"], "spline_length_cm": g["spline_length_cm"],
                       "stations": g["stations"], "foreign_records": foreign,
                       "unacknowledged_foreign_records": unacked,
                       "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
        if mode == "DRY":
            for b in plan["bays"]:
                _log("%s_DRY_BAY|run=%s|%s|B%s|d=%.1f|frac=%.4f|selected=%d"
                     % (MARK, run, b["cue_label"], b["bay_token"], b["distance_cm"], b["fraction"], int(b["selected"])))
            for t in plan["targets"]:
                _log("%s_DRY_ROW|run=%s|%s|%s|%s|%s->%s|frac=%.3f%s"
                     % (MARK, run, t["attachment_label"], t["kind"], t["path"], _short(t["before"]),
                        _short(t["after"]), t["fraction"], "|struck_only" if t.get("struck_only") else ""))
            for w in plan["warnings"]:
                _log("%s_WARNING|run=%s|%s" % (MARK, run, w))
            census_after = tool._dirty_census()
            require(census_after == census_before, "DRY_CENSUS_CHANGED|before=%s|after=%s"
                    % (_canonical(census_before), _canonical(census_after)))
            require(tool._outside_hash(_plain_again(rp, tool, show, g, cfg), []) == tool._outside_hash(before_all, []),
                    "DRY_SHOW_ROWS_CHANGED")
            report.update({"ok": True, "mutated": False, "census_after": census_after})
            path = report_path(mode, run)
            tool._write_json(path, report)
            _log("%s_DRY_OK|run=%s|route=%.1f|spline=%.1f|first=%s|counts=%s|warnings=%d|foreign=%d|unacked=%d"
                 "|census_equal=1|mutated=0|report=%s"
                 % (MARK, run, g["route_length_cm"], g["spline_length_cm"], _canonical(plan["first_selected"]),
                    _canonical(plan["counts"]), len(plan["warnings"]), len(foreign), len(unacked), path))
            return report

        # APPLY
        check_expected(plan, args["expected_targets"], args["expected_bays"])
        require(not os.path.exists(RECORD_PATH), "ACTIVE_RECORD_EXISTS|" + RECORD_PATH)
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        backup = tool._backup(BACKUP_STEM + "-", run)
        record = {"schema_version": SCHEMA_VERSION, "status": "prepared", "run": run, "passage": PASSAGE, "backup": backup,
                  "args": args, "plan": plan,
                  "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                  "export_hash_before": texts_hash,
                  "before_cue_rows": {c: before_all[c] for c in plan["target_cue_guids"]},
                  "acknowledged_records": list(args["ack_records"]), "foreign_records": foreign}
        tool._write_json(RECORD_PATH, record, exclusive=True)              # fsynced before any change
        _log("%s_RECORD_WRITTEN|run=%s|path=%s|rows=%d" % (MARK, run, RECORD_PATH, len(plan["targets"])))
        try:
            _write_fields(tool, show, plan["targets"], "after", check_side="before")
            after_all = _plain_again(rp, tool, show, g, cfg)
            problems = scope_problems(before_all, after_all, plan["targets"], "after", diff)
            require(not problems, "SCOPE_CHANGED|%s" % _canonical(problems)[:3000])
            require(tool._outside_hash(after_all, plan["target_cue_guids"]) == record["outside_before_hash"],
                    "OUTSIDE_HASH_CHANGED")
            require(export_hash(rp, rp._export_texts(show), plan["targets"]) == texts_hash,
                    "EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            _write_fields(tool, show, plan["targets"], "before")
            restored = _plain_again(rp, tool, show, g, cfg)
            require(not scope_problems(before_all, restored, plan["targets"], "before", diff), "ROLLBACK_SCOPE")
            record["status"] = "failed_rolled_back_in_memory"
            tool._write_json(RECORD_PATH, record)
            os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
            raise
        record["status"] = "mutated_verified"
        tool._write_json(RECORD_PATH, record)
        materialized = rp._materialize(scores, show, cfg)
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _plain_again(rp, tool, readback, g, cfg)
        problems = scope_problems(before_all, read_all, plan["targets"], "after", diff)
        require(not problems, "READBACK_SCOPE|%s" % _canonical(problems)[:3000])
        require(export_hash(rp, rp._export_texts(readback), plan["targets"]) == texts_hash,
                "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
        saved_census = tool._dirty_census()
        require(saved_census == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _canonical(saved_census))
        record.update({"status": "saved_readback_verified", "materialized": materialized,
                       "after_live": [{"attachment_guid": t["attachment_guid"], "path": t["path"],
                                       "value": get_field(_row(read_all, t), t["path"])} for t in plan["targets"]],
                       "saved_census": saved_census})
        tool._write_json(RECORD_PATH, record)
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized})
        tool._write_json(report_path(mode, run), report)
        c = plan["counts"]
        _log("%s_APPLY_OK|run=%s|targets=%d|rows=%d|intensity=%d|practical=%d|top=%d|drama_rows=%d|strike=%d|ramp=%d"
             "|after_pass=%d|bays=%d|show_saved=1|level_saved=1|readback=1|record=%s"
             % (MARK, run, c["targets"], c["rows"], c["intensity_rows"], c["practical"], c["top"], c["drama_rows"],
                c["strike_fields"], c["ramp_fields"], c["after_pass_fields"], c["bays_selected"], RECORD_PATH))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(mode, run), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s" % (
            MARK, run, mode, int(report["saved"]), report["error"][:1500], "" if report["saved"] else "|NOTHING SAVED"))
        raise


def _revert(args, run, report, rp, scores, tool, cfg, g, live_all):
    require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
    record = tool._read_json(RECORD_PATH)
    check_record(record)
    plan = record["plan"]
    targets = plan["targets"]
    diff = tool._state_differences
    show = g["show"]
    drifts = field_drifts(live_all, targets, "after")
    report["revert_drifts"] = drifts
    require(not drifts, "REVERT_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:4000]))
    texts_hash = export_hash(rp, rp._export_texts(show), plan["targets"])
    backup = tool._backup(BACKUP_STEM + "Revert-", run)
    try:
        _write_fields(tool, show, targets, "before", check_side="after")
        after_all = _plain_again(rp, tool, show, g, cfg)
        problems = scope_problems(live_all, after_all, targets, "before", diff)
        require(not problems, "REVERT_SCOPE|%s" % _canonical(problems)[:3000])
        exact = exact_problems(after_all, targets, "before")
        require(not exact, "REVERT_NOT_EXACT|%s" % _canonical(exact)[:2000])
        require(export_hash(rp, rp._export_texts(show), plan["targets"]) == texts_hash,
                "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
    except Exception:
        _write_fields(tool, show, targets, "after")
        raise
    materialized = rp._materialize(scores, show, cfg)
    tool._save_narrow()
    report["saved"] = True
    readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    read_all = _plain_again(rp, tool, readback, g, cfg)
    problems = scope_problems(live_all, read_all, targets, "before", diff)
    require(not problems, "REVERT_READBACK_SCOPE|%s" % _canonical(problems)[:3000])
    exact = exact_problems(read_all, targets, "before")
    require(not exact, "REVERT_READBACK_NOT_EXACT|%s" % _canonical(exact)[:2000])
    saved_census = tool._dirty_census()
    require(saved_census == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _canonical(saved_census))
    archived = RECORD_PATH + ".reverted-" + run
    record.update({"status": "reverted", "revert_run": run})
    tool._write_json(RECORD_PATH, record)
    os.rename(RECORD_PATH, archived)
    report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized})
    tool._write_json(report_path("REVERT", run), report)
    _log("%s_REVERT_OK|run=%s|targets=%d|exact=1|show_saved=1|level_saved=1|readback=1|archived=%s"
         % (MARK, run, len(targets), archived))
    return report


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    raw = globals().get("P02BRIGHTEN_ARGS")
    try:
        args = check_args(raw)
    except Exception as error:  # noqa: BLE001 - args refusals get the same stop marker
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


if unreal is not None and "P02BRIGHTEN_ARGS" in globals():
    main()
