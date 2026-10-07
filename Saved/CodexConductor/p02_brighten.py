"""P02 brighten second half: DRY / APPLY / REVERT. Raise dead practicals to a low glow and lift the TOP lights of the
P02 bays in the second half of the route. Intensity ONLY.

Gary, 7 Oct (P02, after the straighten + retime to 47.52 s): "Brighten second half". Earlier notes this honours:
dead bulbs must glow minimally (GARY_PIE_NOTES_2026-10-05.md:255), light the wings lurid "from above" / with the
practicals and NO light shooting through L to R (GARY_PIE_NOTES_2026-10-05.md:220-222) -- so BEAM_R and the LOW_SIDE
rows are never written. A live probe at the 60 % still (probe_p02_view.py) read B18-B19 practicals at 0.0 and
88-209 cd and B20-21 (P02_MYSTIC) TOP_L/TOP_R at 0.0.

WHAT IT WRITES (lighting.intensity of existing Show attachments, nothing else: no colour, cone, drama, transform,
enabled; no row added or removed):
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
   "expected_targets": null|int, "expected_bays": null|[labels], "ack_records": [...], "allow_dirty": []}
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
FIELD = "lighting.intensity"
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
}
PARAM_RANGES = {"from_fraction": (0.0, 0.99), "practical_floor": (1.0, 1000.0), "top_scale": (1.0, 4.0),
                "top_floor_cd": (0.0, 500.0), "top_max_cd": (1.0, 1000.0)}
REL_TOL = 1.0e-6
INFERRED = [
    "station n at 250 + 500 (n-1) cm (uniform intervals, passage_slow_walk_P02_latest.json) -> cut between B11/B12",
    "live intensities still equal the 6 Oct record values (p02_rig_pattern_record.json after_cue_rows)",
    "Intensity appears 0/1 times inside each target's Lighting=(..) export group",
    "a raised strike-on-approach lamp (unstruck_intensity_scale 0) only glows once struck",
    "materialize carries the new Show intensity to the spawned light (not read back from components here)",
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
    targets, untouched, warnings = [], [], []
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
    require(targets, "ZERO_TARGETS")
    targets.sort(key=lambda t: (t["show_index"], t["attachment_index"]))
    counts = {"targets": len(targets), "practical": sum(1 for t in targets if t["kind"] == "practical"),
              "top": sum(1 for t in targets if t["kind"] == "top"), "bays_selected": len(selected),
              "bays_total": len(bays), "untouched_listed": len(untouched),
              "struck_only": sum(1 for t in targets if t.get("struck_only"))}
    return {"passage": PASSAGE, "params": copy.deepcopy(p), "route_length_cm": float(route_length_cm),
            "bays": bays, "selected_bays": [b["cue_label"] for b in selected],
            "first_selected": {k: selected[0][k] for k in ("cue_label", "bay_token", "distance_cm", "fraction")},
            "targets": targets, "untouched": untouched, "warnings": warnings, "counts": counts,
            "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
            "target_attachment_guids": sorted({t["attachment_guid"] for t in targets}),
            "inferred": list(INFERRED)}


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


def apply_rows(all_rows, targets, side):
    require(side in ("before", "after"), "SIDE_INVALID|%s" % side)
    out = copy.deepcopy(all_rows)
    for t in targets:
        _row(out, t)["lighting"]["intensity"] = t[side]
    return out


def scope_problems(base_all, live_all, targets, side, diff):
    """[] iff live == base with exactly the targets' lighting.intensity at their side value."""
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    want_all = apply_rows(base_all, targets, side)
    written = {t["attachment_guid"] for t in targets}
    problems = []
    for cue_guid in sorted(base_all):
        want, got = want_all[cue_guid], live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in got]:
            problems.append({"cue": cue_guid, "problem": "ROW_SET_OR_ORDER_CHANGED"})
            continue
        for w, g in zip(want, got):
            w2, g2 = copy.deepcopy(w), copy.deepcopy(g)
            if w["guid"] in written:
                if not close(g2["lighting"]["intensity"], w2["lighting"]["intensity"]):
                    problems.append({"cue": cue_guid, "guid": w["guid"], "path": FIELD,
                                     "want": w2["lighting"]["intensity"], "got": g2["lighting"]["intensity"]})
                w2["lighting"]["intensity"] = g2["lighting"]["intensity"] = None
            d = diff(w2, g2)
            if d:
                problems.append({"cue": cue_guid, "guid": w["guid"], "label": w["label"], "differences": d})
    return problems


def field_drifts(all_rows, targets, side="after"):
    """Every target whose live intensity != its side value (all of them, not the first)."""
    out = []
    for t in targets:
        hits = [r for r in all_rows.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
        if len(hits) != 1:
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "live": "count=%d" % len(hits)})
            continue
        live = hits[0]["lighting"]["intensity"]
        if not close(live, t[side]):
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "record": t[side], "live": live})
    return out


def exact_problems(all_rows, targets, side):
    """Bit-exact check (REVERT restores the recorded float32 exactly)."""
    return [{"label": t["attachment_label"], "want": t[side], "got": _row(all_rows, t)["lighting"]["intensity"]}
            for t in targets if float(_row(all_rows, t)["lighting"]["intensity"]) != float(t[side])]


def check_record(record):
    require(record.get("passage") == PASSAGE and (record.get("plan") or {}).get("passage") == PASSAGE,
            "RECORD_PASSAGE_MISMATCH|%s" % record.get("passage"))
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|%s" % record.get("status"))
    require(record["plan"].get("targets"), "RECORD_NO_TARGETS")


# --------------------------------------------------------------------------
# Export text scope: mask only the targets' Intensity inside their Lighting=(..) group.
# --------------------------------------------------------------------------
def normalize_export(rp, texts, target_guids):
    wanted = {g.upper() for g in target_guids}
    seen = {g: 0 for g in wanted}
    out = []
    for text in texts:
        marks = list(rp._OWN_GUID.finditer(text))
        pieces, cursor = [], 0
        for index, match in enumerate(marks):
            guid = match.group(1).upper()
            if guid not in wanted:
                continue
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            pieces.append(text[cursor:match.start()])
            pieces.append(rp._mask_intensity(text[match.start():end], guid, "Intensity"))
            cursor = end
            seen[guid] += 1
        pieces.append(text[cursor:])
        out.append("".join(pieces))
    require(all(c == 1 for c in seen.values()), "EXPORT_TARGET_COUNT|%s" % _canonical({g: c for g, c in seen.items()
                                                                                       if c != 1}))
    return out


def export_hash(rp, texts, target_guids):
    return _sha256_text("\n".join(normalize_export(rp, texts, target_guids)))


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


def _write_intensity(tool, show, targets, side, check_side=None):
    """p03_atmos.py:1282-1306 (_write_fields) for the one field lighting.intensity."""
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
        for t in items:
            hits = [a for a in attachments
                    if tool._guid_text(a.get_editor_property("attachment_guid")) == t["attachment_guid"]]
            require(len(hits) == 1, "TARGET_ATTACHMENT_RESOLVE|" + t["attachment_guid"])
            attachment = hits[0]
            require(str(attachment.get_editor_property("label")) == t["attachment_label"],
                    "TARGET_ATTACHMENT_LABEL_DRIFT|" + t["attachment_guid"])
            lighting = attachment.get_editor_property("lighting")
            if check_side is not None:
                live = float(lighting.get_editor_property("intensity"))
                require(close(live, t[check_side]), "TARGET_INTENSITY_DRIFT|%s|live=%r|want=%r"
                        % (t["attachment_label"], live, t[check_side]))
            lighting.set_editor_property("intensity", float(t[side]))
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
        texts_hash = export_hash(rp, rp._export_texts(show), plan["target_attachment_guids"])
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
                _log("%s_DRY_ROW|run=%s|%s|%s|%.4g->%.4g|frac=%.3f%s"
                     % (MARK, run, t["attachment_label"], t["kind"], t["before"], t["after"], t["fraction"],
                        "|struck_only" if t.get("struck_only") else ""))
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
        record = {"schema_version": 1, "status": "prepared", "run": run, "passage": PASSAGE, "backup": backup,
                  "args": args, "plan": plan,
                  "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                  "export_hash_before": texts_hash,
                  "before_cue_rows": {c: before_all[c] for c in plan["target_cue_guids"]},
                  "acknowledged_records": list(args["ack_records"]), "foreign_records": foreign}
        tool._write_json(RECORD_PATH, record, exclusive=True)              # fsynced before any change
        _log("%s_RECORD_WRITTEN|run=%s|path=%s|rows=%d" % (MARK, run, RECORD_PATH, len(plan["targets"])))
        try:
            _write_intensity(tool, show, plan["targets"], "after", check_side="before")
            after_all = _plain_again(rp, tool, show, g, cfg)
            problems = scope_problems(before_all, after_all, plan["targets"], "after", diff)
            require(not problems, "SCOPE_CHANGED|%s" % _canonical(problems)[:3000])
            require(tool._outside_hash(after_all, plan["target_cue_guids"]) == record["outside_before_hash"],
                    "OUTSIDE_HASH_CHANGED")
            require(export_hash(rp, rp._export_texts(show), plan["target_attachment_guids"]) == texts_hash,
                    "EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            _write_intensity(tool, show, plan["targets"], "before")
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
        require(export_hash(rp, rp._export_texts(readback), plan["target_attachment_guids"]) == texts_hash,
                "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
        saved_census = tool._dirty_census()
        require(saved_census == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _canonical(saved_census))
        record.update({"status": "saved_readback_verified", "materialized": materialized,
                       "after_intensity_live": {t["attachment_guid"]: _row(read_all, t)["lighting"]["intensity"]
                                                for t in plan["targets"]},
                       "saved_census": saved_census})
        tool._write_json(RECORD_PATH, record)
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized})
        tool._write_json(report_path(mode, run), report)
        _log("%s_APPLY_OK|run=%s|rows=%d|practical=%d|top=%d|bays=%d|show_saved=1|level_saved=1|readback=1|record=%s"
             % (MARK, run, plan["counts"]["targets"], plan["counts"]["practical"], plan["counts"]["top"],
                plan["counts"]["bays_selected"], RECORD_PATH))
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
    texts_hash = export_hash(rp, rp._export_texts(show), plan["target_attachment_guids"])
    backup = tool._backup(BACKUP_STEM + "Revert-", run)
    try:
        _write_intensity(tool, show, targets, "before", check_side="after")
        after_all = _plain_again(rp, tool, show, g, cfg)
        problems = scope_problems(live_all, after_all, targets, "before", diff)
        require(not problems, "REVERT_SCOPE|%s" % _canonical(problems)[:3000])
        exact = exact_problems(after_all, targets, "before")
        require(not exact, "REVERT_NOT_EXACT|%s" % _canonical(exact)[:2000])
        require(export_hash(rp, rp._export_texts(show), plan["target_attachment_guids"]) == texts_hash,
                "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
    except Exception:
        _write_intensity(tool, show, targets, "after")
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
    _log("%s_REVERT_OK|run=%s|rows=%d|exact=1|show_saved=1|level_saved=1|readback=1|archived=%s"
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
