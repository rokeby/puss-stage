"""Dead bulbs warm: DRY / APPLY / REVERT. Recolour the COOL dead/practical bulbs of P01-P06 to a stable warm mix
(orange / warm white / pink) and give the ones at 0 a tiny glow. Colour, use_temperature, temperature (+ intensity
only where it is 0). Modelled on p02_brighten.py (copied, not edited).

Gary, 7 Oct (his own answer): dead bulbs -> "Warm mix orange/white/pink", ALL passages. His 6 Oct note: if they are
dead bulbs they should at least look like lightbulbs; a bulb can still glow orange, white or pink and cast a small
reflection. Today P02/P04/P06 PRACTICAL_BULB_DEAD rows are rgb [0.55,0.70,1.0] at 6500 K (p02_brighten DRY warnings).

SELECTION RULE (pure, build_plan; every exclusion is listed in plan.untouched with its reason):
  1. the row sits in a bay cue of a selected passage (Show passage_settings label "Passage N" ->
     GetWingPairCueGuidsInPassage), and its label matches LABEL_RE "<P0N> SCORE|LOOK B## <look> <ROLE>" with P0N == that
     passage;
  2. ROLE matches PRACTICAL_RE ^PRACTICAL(_[A-Z0-9]+)*$ and does not end _BODY / _CAP (props, never lights);
  3. it is DEAD: ROLE matches DEAD_ROLE_RE ^PRACTICAL(_[A-Z0-9]+)*_DEAD$ (PRACTICAL_BULB_DEAD, PRACTICAL_DEAD,
     PRACTICAL_CAGE_DEAD) OR its intensity < params.dead_below_lm (default 40 lm) -- else NOT_DEAD;
  4. kind LIGHT, enabled, intensity_units == params.units (LUMENS), not FORBIDDEN_TARGET_LABEL
     (strobe|moon|halo|opening|walkin|flare), not in skip_labels, its cue not a P06 events-owned cue
     (lighting_scores_record_P06.json plan.yield_to_events.cue_guids) unless include_protected;
  5. it is COOL: (use_temperature and temperature_kelvin > params.cool_kelvin (4000)) OR rgb blue-dominant (B > R)
     -- else ALREADY_WARM (P01's 2700 K, P03/P05's 3300-3400 K bulbs stay as they are).
VALUES: palette index = sha256("<seed>|<GUID upper>") first 8 hex mod 3 (ONE draw per statement, no RNG stream):
  0 orange      colour [1,1,1] (alpha kept), use_temperature True, 2200 K
  1 warm_white  colour [1,1,1] (alpha kept), use_temperature True, 2900 K
  2 pink        colour [1.0,0.55,0.7] (alpha kept), use_temperature False, temperature kept (ignored when off)
  intensity: written ONLY when it is exactly 0 -> params.glow_floor_lm (40); otherwise untouched. Nothing else is
  written: no position, cone, drama, enabled, row add/remove. A target records only the fields whose value changes.

GUARDS (APPLY): confirm "APPLY DEADBULBSWARM"; expected_targets (the DRY count) REQUIRED; optional
expected_per_passage; no PIE, no open Sequencer, no ZZ_ actors, clean census (p01_rig_pattern.check_context); no active
record; every foreign active record naming a target GUID acked VERBATIM (p02_brighten_record.json among them: P02
B12-B19 dead bulbs hold its 800 lm; this tool leaves that intensity alone and only recolours them). Then
Backups/PreDeadBulbsWarm-<run> (Show + level), exclusive fsynced record with every before value BEFORE the first write,
write, scope check (every row of every cue == before except exactly the targets' written fields; outside hash; export
text with only the targets' written Lighting fields removed), materialize every affected Passage (+ structure refit),
narrow save (Show + level), read back from the saved asset, status saved_readback_verified. Failure before save rolls
back in memory. REVERT: confirm "REVERT DEADBULBSWARM"; drift check (every written field must still read its after
value, ALL drifts listed); writes the before values, bit-exact in memory and after read-back; archives the record.

Proof tiers (AGENTS.md), per claim:
* declaration-proven: FInfinityStageLightSettings Intensity float (InfinityStageTypes.h:204), Color FLinearColor
  (:207), bUseTemperature bool default false (:210), TemperatureKelvin float 1000-15000 default 6500 (:212-214);
  IntensityUnits enum (:174-181). Python names color / use_temperature / temperature_kelvin are the names written live
  by lighting_looks_apply.py:1511-1513 and read by _infinity_attachment_state.py:7-9 (LIGHT_FIELDS).
  _set_pair_attachments (lighting_looks_apply.py:1292-1300), _save_narrow (:1657-1667), _backup (:1616-1632),
  _materialize_passage / _count_passage_actors (lighting_scores_apply.py:2879-2904), scan_foreign_records skips
  TERMINAL_STATUSES (lighting_scores_apply.py:1966-1995), _bay_guids / _export_texts / check_context
  (p01_rig_pattern.py:1000-1038, :854-867).
* measured (earlier live runs of the reused code): attachment lighting read/modify/write (p02_brighten APPLY
  20261007-022814, saved_readback_verified); colour + use_temperature + temperature writes (lighting_looks_apply.py
  _make_light, live 4-5 Oct). Offline, files read 7 Oct: the cool dead bulbs in lighting_scores_record_P02/P04/P06.json,
  p0N_rig_pattern_record.json after_cue_rows, p02_brighten_record.json (B12-B19 BULB_DEAD 0 -> 800 lm, blue).
* inferred (the DRY confirms each; also in report "inferred"): see INFERRED below.

Args (dead_bulbs_warm_args.json via dead_bulbs_warm_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> DEADBULBSWARM", "params": {...DEFAULTS overrides},
   "expected_targets": null|int, "expected_per_passage": null|{"P02": n, ...}, "ack_records": [...],
   "allow_dirty": []}
Markers: DEADBULBSWARM_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|...; any stop DEADBULBSWARM_STOPPED|run=<id>|<reason>.
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
import struct
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
RIG_PATTERN_PATH = os.path.join(HERE, "p01_rig_pattern.py")
RECORD_PATH = os.path.join(HERE, "dead_bulbs_warm_record.json")
P02_BRIGHTEN_RECORD = os.path.join(HERE, "p02_brighten_record.json")
MARK = "DEADBULBSWARM"
CONFIRM_TOKEN = "DEADBULBSWARM"
VALID_MODES = ("DRY", "APPLY", "REVERT")
ALL_PASSAGES = ("P01", "P02", "P03", "P04", "P05", "P06")
BACKUP_STEM = "PreDeadBulbsWarm"
UNIT_NAMES = ("UNITLESS", "CANDELAS", "LUMENS", "EV", "NITS")   # InfinityStageTypes.h:174-181
LABEL_RE = re.compile(r"^(P0[1-6]) (?:SCORE|LOOK) B(\d{2}) (\S+) (\S+)$")
PRACTICAL_RE = re.compile(r"^PRACTICAL(_[A-Z0-9]+)*$")
DEAD_ROLE_RE = re.compile(r"^PRACTICAL(_[A-Z0-9]+)*_DEAD$")
PROP_SUFFIXES = ("_BODY", "_CAP")
# Written fields: (row field, export UPROPERTY name). Export names from InfinityStageTypes.h:204-214.
FIELDS = (("intensity", "Intensity"), ("color", "Color"), ("use_temperature", "bUseTemperature"),
          ("temperature_kelvin", "TemperatureKelvin"))
FIELD_NAMES = tuple(f for f, unused in FIELDS)
EXPORT_NAME = dict(FIELDS)
PALETTE = (   # Gary 7 Oct: "Warm mix orange/white/pink"
    {"name": "orange", "color": (1.0, 1.0, 1.0), "use_temperature": True, "temperature_kelvin": 2200.0},
    {"name": "warm_white", "color": (1.0, 1.0, 1.0), "use_temperature": True, "temperature_kelvin": 2900.0},
    {"name": "pink", "color": (1.0, 0.55, 0.7), "use_temperature": False, "temperature_kelvin": None},
)
DEFAULTS = {
    "passages": list(ALL_PASSAGES),
    "seed": 20261007,
    "glow_floor_lm": 40.0,          # Gary: dead bulbs should glow; only written where intensity is exactly 0
    "dead_below_lm": 40.0,          # a practical below this counts as dead (rule 3)
    "cool_kelvin": 4000.0,          # rule 5
    "units": "LUMENS",              # every practical in the records is a POINT light in LUMENS (7 Oct survey)
    "include_protected": False,     # P06 events-owned cues (lighting_events_apply.py) stay out by default
    "skip_labels": [],
}
PARAM_RANGES = {"glow_floor_lm": (1.0, 400.0), "dead_below_lm": (0.0, 400.0), "cool_kelvin": (2000.0, 15000.0)}
REL_TOL = 1.0e-6
INFERRED = [
    "live rows still equal the last records (scores/rig_pattern/p02_brighten); hand edits after them change the plan",
    "P05 passage names (label 'Passage 5', actor 'Passage 05', 'Infinity Stage - Structure 05') follow the P01-P06 "
    "format (p01_rig_pattern.passage_config excludes P05; label read from lighting_scores_record_P05.json)",
    "ExportText spells the fields Intensity / Color=(R=,G=,B=,A=) / bUseTemperature / TemperatureKelvin and omits "
    "defaults (0 or 1 occurrence per Lighting group)",
    "use_temperature True multiplies the colour by the blackbody tint, so white + 2200 K reads orange on screen",
    "a strike-on-approach bulb (unstruck_intensity_scale 0) only shows its glow floor once struck",
    "materialize carries the new Show colour/intensity to the spawned lights (not read back from components)",
    "40 lm on a point light is a visible glow at the camera's exposure (not measured; a PIE still decides)",
]


class DeadBulbsWarmError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise DeadBulbsWarmError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def report_path(mode, run, folder=None):
    return os.path.join(folder or HERE, "dead_bulbs_warm_report_%s_%s.json" % (mode, run))


def f32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def close(a, b, tol=REL_TOL):
    a, b = float(a), float(b)
    return abs(a - b) <= tol * max(abs(a), abs(b), 1.0e-3)


# --------------------------------------------------------------------------
# p01_rig_pattern.py reused by import (never edited, never its main()), as p02_brighten.py:148-189.
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


RIG_PATTERN_API = ("load_modules", "passage_config", "load_aims", "load_protected", "_bay_guids", "_ctx_facts",
                   "check_context", "_export_texts", "_close_paren")


def load_rig_pattern():
    rp = load_without_main(RIG_PATTERN_PATH, "_p01_rig_pattern_for_dead_bulbs_warm")
    missing = [n for n in RIG_PATTERN_API if not callable(getattr(rp, n, None))]
    missing += [n for n in ("_OWN_GUID", "_LIGHTING_OPEN", "FORBIDDEN_TARGET_LABEL", "VALID_PASSAGES")
                if not hasattr(rp, n)]
    require(not missing, "RIG_PATTERN_API_DRIFT|" + ",".join(missing))
    return rp


def passage_cfg(rp, key):
    """rp.passage_config for P01-P04/P06; P05 (absent from rp.VALID_PASSAGES) built in the same format (inferred)."""
    require(key in ALL_PASSAGES, "PASSAGE_INVALID|%r" % (key,))
    number = int(key[1:])
    own = {"key": key, "label": "Passage %d" % number, "actor_prefix": "Passage %02d" % number,
           "structure_label": "Infinity Stage - Structure %02d" % number,
           "scores_record": os.path.join(HERE, "lighting_scores_record_%s.json" % key), "inferred_names": True}
    if key in rp.VALID_PASSAGES:
        theirs = rp.passage_config(key)
        for name in ("label", "actor_prefix", "structure_label", "scores_record"):
            require(os.path.normcase(str(theirs[name])) == os.path.normcase(str(own[name])),
                    "PASSAGE_CFG_DRIFT|%s|%s|%r!=%r" % (key, name, theirs[name], own[name]))
        own["inferred_names"] = False
    return own


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
    passages = p["passages"]
    require(isinstance(passages, list) and passages and all(x in ALL_PASSAGES for x in passages)
            and len(set(passages)) == len(passages), "PARAM_PASSAGES|%r" % (passages,))
    p["passages"] = sorted(passages)
    require(isinstance(p["seed"], int) and not isinstance(p["seed"], bool), "PARAM_SEED|%r" % (p["seed"],))
    require(p["units"] in UNIT_NAMES, "PARAM_UNITS|%r" % (p["units"],))
    require(isinstance(p["include_protected"], bool), "PARAM_INCLUDE_PROTECTED|%r" % (p["include_protected"],))
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
    per = args.get("expected_per_passage")
    require(per is None or (isinstance(per, dict) and all(k in ALL_PASSAGES and isinstance(v, int)
                                                          and not isinstance(v, bool) for k, v in per.items())),
            "EXPECTED_PER_PASSAGE_INVALID|%r" % (per,))
    acks = list(args.get("ack_records", []) or [])
    require(all(isinstance(a, str) for a in acks), "ACK_RECORDS_INVALID")
    return {"mode": mode, "confirm": args.get("confirm"), "params": check_params(args.get("params")),
            "expected_targets": expected, "expected_per_passage": None if per is None else dict(per),
            "ack_records": acks, "allow_dirty": list(args.get("allow_dirty", []) or [])}


# --------------------------------------------------------------------------
# Plan (pure).
# --------------------------------------------------------------------------
def palette_index(seed, guid):
    """One hash draw per statement (memory: two draws in one expression have unspecified order)."""
    digest = hashlib.sha256(("%d|%s" % (int(seed), str(guid).upper())).encode("ascii")).hexdigest()
    return int(digest[:8], 16) % len(PALETTE)


def is_cool(lighting, cool_kelvin):
    rgb = list(lighting.get("color") or [])[:3]
    hot = bool(lighting.get("use_temperature")) and float(lighting.get("temperature_kelvin") or 0.0) > cool_kelvin
    blue = len(rgb) == 3 and float(rgb[2]) > float(rgb[0])
    return hot or blue


def warm_values(row, params):
    """{field: [before, after]} for the fields that change; the palette choice."""
    lighting = row["lighting"]
    index = palette_index(params["seed"], row["guid"])
    swatch = PALETTE[index]
    before_color = [float(c) for c in lighting["color"]]
    require(len(before_color) == 4, "COLOR_SHAPE|%s|%r" % (row["label"], lighting["color"]))
    after_color = [f32(swatch["color"][0]), f32(swatch["color"][1]), f32(swatch["color"][2]), before_color[3]]
    before_k = _finite(lighting["temperature_kelvin"], "TEMPERATURE_BEFORE")
    after_k = before_k if swatch["temperature_kelvin"] is None else f32(swatch["temperature_kelvin"])
    before_i = _finite(lighting["intensity"], "INTENSITY_BEFORE")
    require(before_i >= 0.0, "INTENSITY_NEGATIVE|%s|%s" % (row["label"], before_i))
    after_i = f32(params["glow_floor_lm"]) if before_i == 0.0 else before_i
    pairs = {"intensity": [before_i, after_i], "color": [before_color, after_color],
             "use_temperature": [bool(lighting["use_temperature"]), bool(swatch["use_temperature"])],
             "temperature_kelvin": [before_k, after_k]}
    writes = {f: v for f, v in pairs.items() if v[0] != v[1]}
    return swatch["name"], writes


def build_plan(plain, params, forbidden=None, protected=()):
    """plain = {"cues": [{guid,label,show_index,attachments}], "passages": {P0N: {"bay_guids": [...]}}}."""
    p = params
    skip = set(p["skip_labels"])
    protected = {g.upper() for g in protected}
    by_cue = {c["guid"]: c for c in plain["cues"]}
    all_guids = [r["guid"] for c in plain["cues"] for r in c["attachments"]]
    targets, untouched, warnings = [], [], []
    per = {}
    for key in p["passages"]:
        require(key in plain["passages"], "PASSAGE_NOT_GATHERED|" + key)
        bays = plain["passages"][key]["bay_guids"]
        missing = [g for g in bays if g not in by_cue]
        require(not missing, "BAY_GUID_UNRESOLVED|%s|%s" % (key, missing))
        stats = per.setdefault(key, {"targets": 0, "glow_floor": 0, "palette": {s["name"]: 0 for s in PALETTE},
                                     "already_warm": 0, "bays": len(bays)})
        for cue_guid in bays:
            cue = by_cue[cue_guid]
            require(str(cue["label"]).startswith(key + " "), "BAY_NOT_%s|%s" % (key, cue["label"]))
            for index, row in enumerate(cue["attachments"]):
                m = LABEL_RE.match(str(row["label"]))
                if not m:
                    continue
                role = m.group(4)
                if not PRACTICAL_RE.match(role) or role.endswith(PROP_SUFFIXES):
                    continue
                if m.group(1) != key:
                    untouched.append({"cue_label": cue["label"], "label": row["label"], "why": "LABEL_PASSAGE_MISMATCH"})
                    continue
                lighting = row["lighting"]
                intensity = lighting.get("intensity")
                dead = bool(DEAD_ROLE_RE.match(role)) or (intensity is not None
                                                          and float(intensity) < p["dead_below_lm"])
                why = None
                if not dead:
                    why = "NOT_DEAD"
                elif _enum_name(row["kind"]) != "LIGHT":
                    why = "NOT_A_LIGHT"
                elif row["label"] in skip:
                    why = "SKIP_LABEL"
                elif forbidden is not None and forbidden.search(str(row["label"])):
                    why = "FORBIDDEN_LABEL"
                elif cue_guid.upper() in protected and not p["include_protected"]:
                    why = "PROTECTED_EVENTS_CUE"
                elif not row.get("enabled", True):
                    why = "DISABLED"
                elif _enum_name(lighting.get("intensity_units")) != p["units"]:
                    why = "UNITS_MISMATCH"
                elif not is_cool(lighting, p["cool_kelvin"]):
                    why = "ALREADY_WARM"
                if why is not None:
                    if why == "ALREADY_WARM":
                        stats["already_warm"] += 1
                    if why != "NOT_DEAD":
                        untouched.append({"cue_label": cue["label"], "label": row["label"], "role": role, "why": why,
                                          "intensity": intensity, "color": lighting.get("color"),
                                          "temperature_kelvin": lighting.get("temperature_kelvin"),
                                          "use_temperature": lighting.get("use_temperature")})
                    if why == "UNITS_MISMATCH":
                        warnings.append("UNITS_MISMATCH|%s|%s" % (row["label"], lighting.get("intensity_units")))
                    continue
                require(all_guids.count(row["guid"]) == 1, "TARGET_GUID_NOT_UNIQUE|" + row["guid"])
                swatch, writes = warm_values(row, p)
                require(writes, "TARGET_WITHOUT_WRITES|" + row["label"])
                t = {"passage": key, "cue_guid": cue_guid, "cue_label": cue["label"], "show_index": cue["show_index"],
                     "bay_token": m.group(2), "attachment_guid": row["guid"], "attachment_label": row["label"],
                     "attachment_index": index, "role": role, "look": m.group(3), "swatch": swatch,
                     "writes": writes, "glow_floor": "intensity" in writes}
                drama = lighting.get("drama") or {}
                if drama.get("strike_on_approach") and float(drama.get("unstruck_intensity_scale", 1.0)) == 0.0:
                    t["struck_only"] = True
                targets.append(t)
                stats["targets"] += 1
                stats["palette"][swatch] += 1
                stats["glow_floor"] += int(t["glow_floor"])
    targets.sort(key=lambda t: (t["show_index"], t["attachment_index"]))
    require(targets, "ZERO_TARGETS")
    counts = {"targets": len(targets), "glow_floor": sum(1 for t in targets if t["glow_floor"]),
              "struck_only": sum(1 for t in targets if t.get("struck_only")),
              "untouched_listed": len(untouched),
              "palette": {s["name"]: sum(1 for t in targets if t["swatch"] == s["name"]) for s in PALETTE}}
    return {"params": copy.deepcopy(p), "targets": targets, "untouched": untouched, "warnings": warnings,
            "counts": counts, "per_passage": per,
            "affected_passages": sorted({t["passage"] for t in targets}),
            "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
            "target_attachment_guids": sorted({t["attachment_guid"] for t in targets}),
            "inferred": list(INFERRED)}


def overlap_with_record(plan, record):
    """Targets also written by another tool's ACTIVE record (e.g. p02_brighten: P02 B12-B19 at 800 lm)."""
    if not record or str(record.get("status", "")).lower() in ("reverted", "failed_rolled_back_in_memory",
                                                                "stale", "superseded"):
        return []
    theirs = {t["attachment_guid"]: t for t in (record.get("plan") or {}).get("targets", [])}
    out = []
    for t in plan["targets"]:
        if t["attachment_guid"] in theirs:
            out.append({"label": t["attachment_label"], "their_fields": [theirs[t["attachment_guid"]].get("path")],
                        "their_after": theirs[t["attachment_guid"]].get("after"),
                        "our_fields": sorted(t["writes"])})
    return out


def check_expected(plan, expected_targets, expected_per_passage):
    if expected_targets is not None:
        require(plan["counts"]["targets"] == expected_targets,
                "EXPECTED_TARGETS|expected=%s|planned=%d" % (expected_targets, plan["counts"]["targets"]))
    if expected_per_passage is not None:
        got = {k: v["targets"] for k, v in plan["per_passage"].items() if v["targets"]}
        want = {k: v for k, v in expected_per_passage.items() if v}
        require(got == want, "EXPECTED_PER_PASSAGE|expected=%s|planned=%s" % (_canonical(want), _canonical(got)))


# --------------------------------------------------------------------------
# Rows model, scope, drift (pure).
# --------------------------------------------------------------------------
def _row(all_rows, t):
    hits = [r for r in all_rows.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
    require(len(hits) == 1, "TARGET_ROW_RESOLVE|%s|count=%d" % (t["attachment_guid"], len(hits)))
    return hits[0]


def _side(t, field, side):
    require(side in ("before", "after"), "SIDE_INVALID|%s" % side)
    return t["writes"][field][0 if side == "before" else 1]


def apply_rows(all_rows, targets, side):
    out = copy.deepcopy(all_rows)
    for t in targets:
        lighting = _row(out, t)["lighting"]
        for field in t["writes"]:
            lighting[field] = copy.deepcopy(_side(t, field, side))
    return out


def value_close(field, a, b, exact=False):
    if field == "use_temperature":
        return bool(a) == bool(b) and isinstance(a, bool) == isinstance(b, bool)
    if field == "color":
        return (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)
                and all((float(x) == float(y)) if exact else close(x, y) for x, y in zip(a, b)))
    return float(a) == float(b) if exact else close(a, b)


def scope_problems(base_all, live_all, targets, side, diff):
    """[] iff live == base with exactly the targets' written fields at their side value."""
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    want_all = apply_rows(base_all, targets, side)
    written = {t["attachment_guid"]: t for t in targets}
    problems = []
    for cue_guid in sorted(base_all):
        want, got = want_all[cue_guid], live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in got]:
            problems.append({"cue": cue_guid, "problem": "ROW_SET_OR_ORDER_CHANGED"})
            continue
        for w, g in zip(want, got):
            w2, g2 = copy.deepcopy(w), copy.deepcopy(g)
            t = written.get(w["guid"])
            if t is not None:
                for field in t["writes"]:
                    if not value_close(field, g2["lighting"].get(field), w2["lighting"][field]):
                        problems.append({"cue": cue_guid, "guid": w["guid"], "path": "lighting." + field,
                                         "want": w2["lighting"][field], "got": g2["lighting"].get(field)})
                    w2["lighting"][field] = g2["lighting"][field] = None
            d = diff(w2, g2)
            if d:
                problems.append({"cue": cue_guid, "guid": w["guid"], "label": w["label"], "differences": d})
    return problems


def field_drifts(all_rows, targets, side="after"):
    """Every (target, field) whose live value != its side value -- all of them, not the first."""
    out = []
    for t in targets:
        hits = [r for r in all_rows.get(t["cue_guid"], []) if r["guid"] == t["attachment_guid"]]
        if len(hits) != 1:
            out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "live": "count=%d" % len(hits)})
            continue
        for field in sorted(t["writes"]):
            live = hits[0]["lighting"].get(field)
            if not value_close(field, live, _side(t, field, side)):
                out.append({"guid": t["attachment_guid"], "label": t["attachment_label"], "field": field,
                            "record": _side(t, field, side), "live": live})
    return out


def exact_problems(all_rows, targets, side):
    """Bit-exact (REVERT restores the recorded float32 values exactly)."""
    out = []
    for t in targets:
        lighting = _row(all_rows, t)["lighting"]
        for field in sorted(t["writes"]):
            if not value_close(field, lighting.get(field), _side(t, field, side), exact=True):
                out.append({"label": t["attachment_label"], "field": field, "want": _side(t, field, side),
                            "got": lighting.get(field)})
    return out


def check_record(record):
    require(record.get("tool") == MARK, "RECORD_TOOL_MISMATCH|%s" % record.get("tool"))
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|%s" % record.get("status"))
    require((record.get("plan") or {}).get("targets"), "RECORD_NO_TARGETS")


# --------------------------------------------------------------------------
# Export text scope: remove only the targets' written top-level fields inside their Lighting=(..) group.
# --------------------------------------------------------------------------
def _value_end(inner, start):
    """End index (exclusive) of a field value starting at inner[start]: a (..) group or up to the next ',' / ')'."""
    if start < len(inner) and inner[start] == "(":
        depth = 0
        for i in range(start, len(inner)):
            if inner[i] == "(":
                depth += 1
            elif inner[i] == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        raise DeadBulbsWarmError("EXPORT_UNBALANCED")
    i = start
    while i < len(inner) and inner[i] not in ",()":
        i += 1
    return i


def mask_fields(rp, segment, guid, names):
    found = list(rp._LIGHTING_OPEN.finditer(segment))
    require(len(found) >= 1, "EXPORT_NO_LIGHTING|guid=" + guid)
    open_at = found[0].end() - 1
    close_at = rp._close_paren(segment, open_at)
    require(close_at is not None, "EXPORT_UNBALANCED|guid=" + guid)
    inner = segment[open_at + 1:close_at]
    for name in names:
        pattern = re.compile(r"(?<![A-Za-z])%s=" % re.escape(name))
        hits = [m for m in pattern.finditer(inner) if inner[:m.start()].count("(") == inner[:m.start()].count(")")]
        # ExportText omits a default-valued field (Color White, bUseTemperature false, TemperatureKelvin 6500), so 0 or
        # 1 hit; the field is REMOVED so before/after texts normalise to the same string either way.
        require(len(hits) <= 1, "EXPORT_%s_COUNT|guid=%s|count=%d" % (name.upper(), guid, len(hits)))
        if hits:
            end = _value_end(inner, hits[0].end())
            if end < len(inner) and inner[end] == ",":
                end += 1
            inner = inner[:hits[0].start()] + inner[end:]
    return segment[:open_at + 1] + inner + segment[close_at:]


def normalize_export(rp, texts, targets):
    wanted = {t["attachment_guid"].upper(): [EXPORT_NAME[f] for f in sorted(t["writes"])] for t in targets}
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
            pieces.append(mask_fields(rp, text[match.start():end], guid, wanted[guid]))
            cursor = end
            seen[guid] += 1
        pieces.append(text[cursor:])
        out.append("".join(pieces))
    require(all(c == 1 for c in seen.values()),
            "EXPORT_TARGET_COUNT|%s" % _canonical({g: c for g, c in seen.items() if c != 1}))
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


def _write_fields(tool, show, targets, side, check_side=None):
    """p02_brighten._write_intensity generalised to the target's written Lighting fields."""
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
            for field in sorted(t["writes"]):
                if check_side is not None:
                    raw = lighting.get_editor_property(field)
                    if field == "color":
                        live = [float(raw.r), float(raw.g), float(raw.b), float(raw.a)]
                    elif field == "use_temperature":
                        live = bool(raw)
                    else:
                        live = float(raw)
                    require(value_close(field, live, _side(t, field, check_side)),
                            "TARGET_%s_DRIFT|%s|live=%r|want=%r" % (field.upper(), t["attachment_label"], live,
                                                                   _side(t, field, check_side)))
                value = _side(t, field, side)
                if field == "color":
                    lighting.set_editor_property("color", unreal.LinearColor(float(value[0]), float(value[1]),
                                                                             float(value[2]), float(value[3])))
                elif field == "use_temperature":
                    lighting.set_editor_property("use_temperature", bool(value))
                elif field == "temperature_kelvin":
                    lighting.set_editor_property("temperature_kelvin", float(value))
                else:
                    lighting.set_editor_property("intensity", float(value))
            attachment.set_editor_property("lighting", lighting)
        tool._set_pair_attachments(show, index, attachments)


def _plain(rp, tool, show, cfgs, record_guids):
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")),
                     "attachments": tool._attachment_rows(tool._pair_attachments(cue))})
    passages = {}
    for key, cfg in cfgs.items():
        guid, bays = rp._bay_guids(tool, show, record_guids.get(key), cfg["label"])
        passages[key] = {"passage_guid": guid, "bay_guids": bays}
    return {"cues": cues, "passages": passages}


def _all_rows(plain):
    return {cue["guid"]: cue["attachments"] for cue in plain["cues"]}


def _materialize(scores, show, cfg):
    prefix = cfg["actor_prefix"]
    require(scores._count_passage_actors(show, prefix) == 1, "PASSAGE_ACTOR_COUNT|" + prefix)
    result = scores._materialize_passage(show, prefix)
    require(result.get("structure") in (None, cfg["structure_label"]), "STRUCTURE_LABEL_UNEXPECTED|%s" % result)
    return result


def _scan_foreign(scores, plan):
    saved = os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, plan["target_attachment_guids"], exclude=[RECORD_PATH])


def _read_p02_brighten():
    if not os.path.isfile(P02_BRIGHTEN_RECORD):
        return None
    with open(P02_BRIGHTEN_RECORD, encoding="utf-8") as handle:
        return json.load(handle)


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False, "inferred": INFERRED}
    tool = None
    try:
        rp = load_rig_pattern()
        scores, tool = rp.load_modules()
        if mode == "REVERT":   # gather exactly the passages the record touched (read again by tool in _revert)
            require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
            with open(RECORD_PATH, encoding="utf-8") as handle:
                keys = list((json.load(handle).get("plan") or {}).get("affected_passages") or [])
            require(keys and all(k in ALL_PASSAGES for k in keys), "RECORD_PASSAGES_INVALID|%r" % (keys,))
        else:
            keys = args["params"]["passages"]
        cfgs = {k: passage_cfg(rp, k) for k in keys}
        record_guids = {k: rp.load_aims(c["scores_record"])[1] for k, c in cfgs.items()}
        protected = rp.load_protected(cfgs["P06"]["scores_record"]) if "P06" in cfgs else []
        report["sources"] = {"rig_pattern_sha256": rp.SOURCE_SHA256, "scores_sha256": scores.SOURCE_SHA256}
        ctx = rp._ctx_facts(tool)
        report["context"] = ctx
        rp.check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        plain = _plain(rp, tool, show, cfgs, record_guids)
        before_all = _all_rows(plain)
        diff = tool._state_differences

        if mode == "REVERT":
            return _revert(run, report, rp, scores, tool, cfgs, record_guids, show, before_all)

        plan = build_plan(plain, args["params"], rp.FORBIDDEN_TARGET_LABEL, protected)
        problems = scope_problems(before_all, apply_rows(before_all, plan["targets"], "after"), plan["targets"],
                                  "after", diff)
        require(not problems, "MODEL_SELF_CHECK|%s" % _canonical(problems)[:2000])
        texts_hash = export_hash(rp, rp._export_texts(show), plan["targets"])
        actors = {k: scores._count_passage_actors(show, cfgs[k]["actor_prefix"]) for k in plan["affected_passages"]}
        require(all(n == 1 for n in actors.values()), "PASSAGE_ACTOR_COUNT|%s" % _canonical(actors))
        foreign = _scan_foreign(scores, plan)
        unacked = unacked_records(foreign, args["ack_records"])
        overlap = overlap_with_record(plan, _read_p02_brighten())
        report.update({"plan": plan, "passage_guids": {k: v["passage_guid"] for k, v in plain["passages"].items()},
                       "passage_actor_counts": actors, "foreign_records": foreign,
                       "unacknowledged_foreign_records": unacked, "p02_brighten_overlap": overlap,
                       "protected_cue_guids": protected,
                       "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
        if mode == "DRY":
            for t in plan["targets"]:
                _log("%s_DRY_ROW|run=%s|%s|%s|%s%s%s" % (
                    MARK, run, t["attachment_label"], t["swatch"], _canonical(t["writes"]),
                    "|glow_floor" if t["glow_floor"] else "", "|struck_only" if t.get("struck_only") else ""))
            for w in plan["warnings"]:
                _log("%s_WARNING|run=%s|%s" % (MARK, run, w))
            census_after = tool._dirty_census()
            require(census_after == census_before, "DRY_CENSUS_CHANGED|before=%s|after=%s"
                    % (_canonical(census_before), _canonical(census_after)))
            require(tool._outside_hash(_all_rows(_plain(rp, tool, show, cfgs, record_guids)), [])
                    == tool._outside_hash(before_all, []), "DRY_SHOW_ROWS_CHANGED")
            report.update({"ok": True, "mutated": False, "census_after": census_after})
            path = report_path(mode, run)
            tool._write_json(path, report)
            _log("%s_DRY_OK|run=%s|counts=%s|per_passage=%s|p02_brighten_overlap=%d|warnings=%d|foreign=%d|unacked=%d"
                 "|census_equal=1|mutated=0|report=%s"
                 % (MARK, run, _canonical(plan["counts"]),
                    _canonical({k: v["targets"] for k, v in plan["per_passage"].items()}), len(overlap),
                    len(plan["warnings"]), len(foreign), len(unacked), path))
            return report

        # APPLY
        check_expected(plan, args["expected_targets"], args["expected_per_passage"])
        require(not os.path.exists(RECORD_PATH), "ACTIVE_RECORD_EXISTS|" + RECORD_PATH)
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        backup = tool._backup(BACKUP_STEM + "-", run)
        record = {"schema_version": 1, "tool": MARK, "status": "prepared", "run": run, "backup": backup,
                  "args": args, "plan": plan, "passages": {k: cfgs[k] for k in plan["affected_passages"]},
                  "record_passage_guids": record_guids,
                  "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                  "export_hash_before": texts_hash,
                  "before_cue_rows": {c: before_all[c] for c in plan["target_cue_guids"]},
                  "acknowledged_records": list(args["ack_records"]), "foreign_records": foreign,
                  "p02_brighten_overlap": overlap}
        tool._write_json(RECORD_PATH, record, exclusive=True)              # fsynced before any change
        _log("%s_RECORD_WRITTEN|run=%s|path=%s|rows=%d" % (MARK, run, RECORD_PATH, len(plan["targets"])))
        try:
            _write_fields(tool, show, plan["targets"], "after", check_side="before")
            after_all = _all_rows(_plain(rp, tool, show, cfgs, record_guids))
            problems = scope_problems(before_all, after_all, plan["targets"], "after", diff)
            require(not problems, "SCOPE_CHANGED|%s" % _canonical(problems)[:3000])
            require(tool._outside_hash(after_all, plan["target_cue_guids"]) == record["outside_before_hash"],
                    "OUTSIDE_HASH_CHANGED")
            require(export_hash(rp, rp._export_texts(show), plan["targets"]) == texts_hash,
                    "EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            _write_fields(tool, show, plan["targets"], "before")
            restored = _all_rows(_plain(rp, tool, show, cfgs, record_guids))
            require(not scope_problems(before_all, restored, plan["targets"], "before", diff), "ROLLBACK_SCOPE")
            record["status"] = "failed_rolled_back_in_memory"
            tool._write_json(RECORD_PATH, record)
            os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
            raise
        record["status"] = "mutated_verified"
        tool._write_json(RECORD_PATH, record)
        materialized = [_materialize(scores, show, cfgs[k]) for k in plan["affected_passages"]]
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _all_rows(_plain(rp, tool, readback, cfgs, record_guids))
        problems = scope_problems(before_all, read_all, plan["targets"], "after", diff)
        require(not problems, "READBACK_SCOPE|%s" % _canonical(problems)[:3000])
        require(export_hash(rp, rp._export_texts(readback), plan["targets"]) == texts_hash,
                "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
        saved_census = tool._dirty_census()
        require(saved_census == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _canonical(saved_census))
        record.update({"status": "saved_readback_verified", "materialized": materialized, "saved_census": saved_census,
                       "after_live": {t["attachment_guid"]: {f: _row(read_all, t)["lighting"][f] for f in t["writes"]}
                                      for t in plan["targets"]}})
        tool._write_json(RECORD_PATH, record)
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized})
        tool._write_json(report_path(mode, run), report)
        _log("%s_APPLY_OK|run=%s|rows=%d|glow_floor=%d|passages=%s|show_saved=1|level_saved=1|readback=1|record=%s"
             % (MARK, run, plan["counts"]["targets"], plan["counts"]["glow_floor"],
                ",".join(plan["affected_passages"]), RECORD_PATH))
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


def _revert(run, report, rp, scores, tool, cfgs, record_guids, show, live_all):
    require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
    record = tool._read_json(RECORD_PATH)
    check_record(record)
    plan = record["plan"]
    targets = plan["targets"]
    diff = tool._state_differences
    drifts = field_drifts(live_all, targets, "after")
    report["revert_drifts"] = drifts
    require(not drifts, "REVERT_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:4000]))
    texts_hash = export_hash(rp, rp._export_texts(show), targets)
    backup = tool._backup(BACKUP_STEM + "Revert-", run)
    try:
        _write_fields(tool, show, targets, "before", check_side="after")
        after_all = _all_rows(_plain(rp, tool, show, cfgs, record_guids))
        problems = scope_problems(live_all, after_all, targets, "before", diff)
        require(not problems, "REVERT_SCOPE|%s" % _canonical(problems)[:3000])
        exact = exact_problems(after_all, targets, "before")
        require(not exact, "REVERT_NOT_EXACT|%s" % _canonical(exact)[:2000])
        require(export_hash(rp, rp._export_texts(show), targets) == texts_hash, "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
    except Exception:
        _write_fields(tool, show, targets, "after")
        raise
    materialized = [_materialize(scores, show, cfgs[k]) for k in plan["affected_passages"]]
    tool._save_narrow()
    report["saved"] = True
    readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    read_all = _all_rows(_plain(rp, tool, readback, cfgs, record_guids))
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
    raw = globals().get("DEADBULBSWARM_ARGS")
    try:
        args = check_args(raw)
    except Exception as error:  # noqa: BLE001 - args refusals get the same stop marker
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


if unreal is not None and "DEADBULBSWARM_ARGS" in globals():
    main()
