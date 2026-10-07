"""P01 rig pattern: DRY / APPLY / REVERT. Copy Gary's hand-placed B03/B04 score-light positions to every P01 bay.

Gary hand-placed the score lights of "P01 Wing 003" (bay B03) and "P01 Wing 004" (B04) and wants every other P01
bay's score lights at the same RELATIVE location + rotation. This tool writes ONLY
relative_transform.location and relative_transform.rotation of named score attachments. Intensity, colour,
cones, attenuation, source size, enabled and scale are never written.

Model. Every P01 bay has a side PARITY: the sign of its live LOW_SIDE_L_KEY relative y (B03 '-', B04 '+',
measured in lighting_drift_report.json run DRIFT-20261006-182900 and lighting_scores_record_P01.json; it
alternates irregularly, so it is always computed from the LIVE row, never from the bay number). Templates are
read LIVE at run time: for each role, the template cue of the same parity supplies relative location and
rotation quaternion; a target role copies it verbatim (no mirroring maths). Roles without a template role, bays
without a LOW_SIDE_L_KEY (practical-only bays), the two template cues, B01/B02 and every (cue, role) in "skip"
are untouched. Optional deterministic jitter: each number comes from its own
random.Random(f"{seed}|{cue_label}|{base_role}|{axis}") (one draw per generator, never two draws in one
expression); a light and its _BODY prop share base_role, so housings keep their bulb's offset.

Copied (not imported) from rig_lamp_drop.py, which is live-proven (APPLY runs 20261005-091147 ..
20261006-022035): require/_canonical/_sha256_text :100-110, quat_mul :185, _enum_name :266, the
scope-guard idea check_scope :552, revert drift/exactness revert_plain :588 / check_revert_drift :580 (here
extended to report ALL drifts), _OWN_GUID export masking normalize_export :608-642 (here masking
Rotation+Translation inside RelativeTransform instead of Translation.Z), check_context :645, module loading
load_without_main :682-749, _ctx_facts :766, _write_z :872 (here _write_transforms, location + rotation),
the APPLY/REVERT sequence of _run :930-1084 (record before first write, rollback in memory on a scope failure,
materialize, _save_narrow, read back).

Proof tiers (AGENTS.md), per claim:
* declaration-proven: attachment rows are S.attachment_state (_infinity_attachment_state.py:104-129) with the
  quaternion canonicalised to a positive first non-zero component (_infinity_attachment_state.py:70-87);
  Translation/Rotation live on FTransform (read as transform.translation / .rotation there, :71-73);
  _set_pair_attachments writes the cue array with show.modify() (lighting_looks_apply.py:1292-1300);
  _save_narrow saves only SHOW_PATH + the current level and refuses any other dirty package
  (lighting_looks_apply.py:1665-1676); _backup copies those two packages into Backups/<prefix><run>
  (lighting_looks_apply.py:1616-1633); _materialize_passage (lighting_scores_apply.py:2879-2896);
  Show passage query get_wing_pair_cue_guids_in_passage (used live at lighting_scores_apply.py:2567).
* measured (offline, 6 Oct, from the files named above): label shape "P01 SCORE B03 P01_WARM_THEATRICAL TOP_L",
  role = last token; label B## is the passage ORDINAL, not the cue-label number ("P01 Wing 011" carries B10);
  practical-only bays carry PRACTICAL_GLIMMER/DEAD only; panel aims target_cm per bay in plan.targets[].aims.
* inferred (the first live DRY/APPLY confirms each; listed in the hand-back): transform.set_editor_property
  ("rotation", unreal.Quat(x, y, z, w)) stores the quaternion exactly (rig_lamp_drop only proved
  "translation"); FTransform export text carries Rotation=(..) and Translation=(..) inside
  RelativeTransform=(..) (rig_lamp_drop proved Translation only); EditorAssetLibrary.load_asset after save
  returns the in-memory object, so "read back" is the saved object, not a disk reload (same as rig_lamp_drop);
  the aims' |target_cm y| is the bay's panel lateral position (PANEL warning is advisory only).

Args (p01_rig_pattern_args.json via p01_rig_pattern_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P01RIGPATTERN",
   "jitter": {"loc_cm": 25, "rot_deg": 3, "seed": 20261006}, "skip": [["P01 Wing 005", "BEAM_R"]],
   "roles": [...], "expected_targets": null|int, "ack_records": [...], "allow_dirty": []}
Markers: P01RIGPATTERN_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|...; any stop P01RIGPATTERN_STOPPED|run=<id>|<reason>.

Other passages (7 Oct, Gary: P02 and P03 "hard reset" to P01's positions, own colours). Extra args
  "target_passage": "P01"|"P02"|"P03" (default P01), "template_passage" (default P01),
  "template_cues" (alias of "templates", default {"-": "P01 Wing 003", "+": "P01 Wing 004"}),
  "no_parity_template": null|"-"|"+" (off-P01 only; default null = bays with no parity role are reported, not moved).
Target P01 is exactly the 6 Oct tool: same record p01_rig_pattern_record.json, marker/confirm P01RIGPATTERN, backup
PreP01RigPattern-, excludes B01/B02, skip B05 BEAM_R, strict LOW_SIDE_L_KEY parity (passage_config("P01") returns the
module constants). Target P0N: record p0N_rig_pattern_record.json, reports p0N_rig_pattern_report_*, marker and
confirm P0NRIGPATTERN, backup PreP0NRigPattern-, no excludes/skips by default; every P0N score cue is a candidate;
templates are resolved LIVE among the template passage's cues (plain["template_bay_guids"]); parity per bay is the
sign of LOW_SIDE_L_KEY y, else LOW_SIDE_R_FILL y inverted, else BEAM_R y (warning PARITY_FALLBACK), else the bay is
NO_PARITY (warning, untouched) unless "no_parity_template" names a template. Missing roles are listed per bay
(missing_roles) and counted per role (plan.role_counts). PANEL_BAND stays advisory, reading the target passage's own
lighting_scores_record_P0N.json aims (P0N panel widths may differ from P01's).
Frame: STATION-anchored rows are composed RelativeTransform * (OccurrenceOffset * spline transform at the wing's
DistanceCm) (declaration-proven, InfinityStagePassageActor.cpp:1881-1885, :1921, :1999), so the stored relative values
do not depend on the route's shape; a route change (P02 straightening) moves the station frames, not these values.
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import math
import os
import random
import re
import struct
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
SCORES_TOOL_PATH = os.path.join(HERE, "lighting_scores_apply.py")
SCORES_RECORD_P01 = os.path.join(HERE, "lighting_scores_record_P01.json")
RECORD_PATH = os.path.join(HERE, "p01_rig_pattern_record.json")
VALID_MODES = ("DRY", "APPLY", "REVERT")
CONFIRM_TOKEN = "P01RIGPATTERN"
MARK = "P01RIGPATTERN"
PASSAGE_KEY = "P01"
PASSAGE_LABEL = "Passage 1"                       # lighting_scores_record_P01.json plan.passage_label (measured)
PASSAGE_ACTOR_PREFIX = "Passage 01"               # rig_lamp_drop.py:80 PASSAGE_ACTOR_PREFIX_FMT % 1
STRUCTURE_LABEL = "Infinity Stage - Structure 01"  # rig_lamp_drop.py:79 STRUCTURE_LABEL_FMT % 1
SCORE_LABEL = re.compile(r"^P01 SCORE B(\d{2}) \S+ (\S+)$")
PARITY_ROLE = "LOW_SIDE_L_KEY"
# Gary 6 Oct: LIGHTS only; *_BODY props stay put (to be replaced by new meshes). A _BODY role may still be
# listed explicitly in args "roles"; it then shares its light's jitter offset (base_role).
DEFAULT_ROLES = ("TOP_L", "TOP_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R",
                 "PRACTICAL_CLAMP", "PRACTICAL_BULB_DEAD")
DEFAULT_JITTER = {"loc_cm": 25.0, "rot_deg": 3.0, "seed": 20261006}   # Gary 6 Oct
DEFAULT_TEMPLATES = {"-": "P01 Wing 003", "+": "P01 Wing 004"}
DEFAULT_EXCLUDE = ("P01 Wing 001", "P01 Wing 002")
DEFAULT_SKIP = (("P01 Wing 005", "BEAM_R"),)      # Gary hand-moved B05's beam
LOC_TOL_CM = 1.0e-6                               # written fields only; everything else is compared exactly
ROT_TOL = 1.0e-6                                   # unreal.Quat round-trips through float32 (measured 6 Oct: ~1e-8)
WRITTEN = ("location", "rotation_xyzw")

# --------------------------------------------------------------------------
# Generalisation (7 Oct, Gary: "P02's lights need a hard reset ... same positions (albeit diff colours) to what
# we have P01 as now"; P03 the same). target_passage P01 keeps every P01 constant above exactly (record path,
# marker, confirm token, backup prefix, excludes, skip, strict parity), so the live P01 record and its REVERT are
# unaffected. Any other target gets its own record/report/marker/confirm/backup names and reads the templates LIVE
# from the template passage's cues (default P01 Wing 003 / 004).
# --------------------------------------------------------------------------
VALID_PASSAGES = ("P01", "P02", "P03", "P04", "P06")
# Off-P01 belt and braces (Gary 7 Oct: P04's moonlight key, strobe and p04_strobe_halo*/opening rows are his):
# a target row's label must match "<P0N> SCORE B## <look> <ROLE>" (score_label) AND must not name any of these.
FORBIDDEN_TARGET_LABEL = re.compile(r"strobe|moon|halo|opening|walkin|flare", re.IGNORECASE)
INTENSITY_SCALE_MAX = 4.0
# cast_shadows (Gary 7 Oct, P06: "shadows casting across the wide central space"): only these moved LIGHT roles.
SHADOW_ROLES = ("TOP_L", "TOP_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R")
# Lighting fields this tool may write besides the transform: (row field, plan guid list, export name, UE property).
# Python names as written live by lighting_looks_apply.py:1509-1511; export names = UPROPERTY names
# (InfinityStageTypes.h:204 Intensity, :239 bCastShadows) - the export spelling is inferred until a live DRY/APPLY.
LIGHTING_FIELDS = (("intensity", "intensity_guids", "Intensity", "intensity"),
                   ("cast_shadows", "shadow_guids", "bCastShadows", "cast_shadows"))
# Passages whose scores record names cues owned by another tool (P06 BLACK-mode bays 2-10, lighting_events_apply.py):
# the guids are read from lighting_scores_record_P0N.json plan.yield_to_events.cue_guids and are never targets.
PROTECTED_FROM_SCORES = ("P06",)
INTENSITY_REL_TOL = 1.0e-6                         # FInfinityStageLightSettings::Intensity is float (InfinityStageTypes.h:204)
PARITY_FALLBACK = (("LOW_SIDE_L_KEY", 1.0), ("LOW_SIDE_R_FILL", -1.0), ("BEAM_R", 1.0))   # role, sign factor


def passage_config(key):
    """Per-passage names. P01 returns the module constants verbatim (live record compatibility)."""
    require(key in VALID_PASSAGES, "PASSAGE_INVALID|%r|valid=%s" % (key, ",".join(VALID_PASSAGES)))
    number = int(key[1:])
    if key == PASSAGE_KEY:
        return {"key": key, "label": PASSAGE_LABEL, "actor_prefix": PASSAGE_ACTOR_PREFIX,
                "structure_label": STRUCTURE_LABEL, "score_label": SCORE_LABEL, "record_path": RECORD_PATH,
                "scores_record": SCORES_RECORD_P01, "mark": MARK, "confirm_token": CONFIRM_TOKEN,
                "file_stem": "p01_rig_pattern", "backup_stem": "PreP01RigPattern"}
    # "Passage %d" plan.passage_label measured in lighting_scores_record_P02/P03.json; actor prefix and structure
    # label formats from rig_lamp_drop.py:79-80 (live-applied on P02/P03, 5-6 Oct).
    return {"key": key, "label": "Passage %d" % number, "actor_prefix": "Passage %02d" % number,
            "structure_label": "Infinity Stage - Structure %02d" % number,
            "score_label": re.compile(r"^%s SCORE B(\d{2}) \S+ (\S+)$" % key),
            "record_path": os.path.join(HERE, "p%02d_rig_pattern_record.json" % number),
            "scores_record": os.path.join(HERE, "lighting_scores_record_%s.json" % key),
            "mark": "%sRIGPATTERN" % key, "confirm_token": "%sRIGPATTERN" % key,
            "file_stem": "p%02d_rig_pattern" % number, "backup_stem": "Pre%sRigPattern" % key}


def mark_for_raw(raw):
    """Marker prefix for a stop before check_args has run (falls back to the P01 marker)."""
    key = (raw or {}).get("target_passage", PASSAGE_KEY) if isinstance(raw, dict) else PASSAGE_KEY
    return "%sRIGPATTERN" % key if key in VALID_PASSAGES else MARK


class P01RigPatternError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise P01RigPatternError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def report_path(mode, run, folder=None, passage=PASSAGE_KEY):
    stem = passage_config(passage)["file_stem"] if passage in VALID_PASSAGES else "p01_rig_pattern"
    return os.path.join(folder or HERE, "%s_report_%s_%s.json" % (stem, mode, run))


def backup_prefix(revert=False, passage=PASSAGE_KEY):
    return "%s%s-" % (passage_config(passage)["backup_stem"], "Revert" if revert else "")


# --------------------------------------------------------------------------
# Quaternion helpers (x, y, z, w; FQuat semantics), rig_lamp_drop.py:185.
# --------------------------------------------------------------------------
def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def canonical_quat(q):
    """_infinity_attachment_state.py:76-81: first non-zero component positive."""
    out = [float(c) for c in q]
    for c in out:
        if c == 0.0:
            continue
        if c < 0.0:
            out = [-v for v in out]
        break
    return out


def quat_close(a, b, tol=ROT_TOL):
    """Same rotation within tol (q and -q are the same rotation)."""
    d1 = max(abs(float(x) - float(y)) for x, y in zip(a, b))
    d2 = max(abs(float(x) + float(y)) for x, y in zip(a, b))
    return min(d1, d2) <= tol


def delta_quat(yaw_deg, pitch_deg):
    """Small local delta: yaw about Z, then pitch about Y (FRotator order yaw*pitch, roll 0)."""
    hy, hp = math.radians(yaw_deg) * 0.5, math.radians(pitch_deg) * 0.5
    q_yaw = [0.0, 0.0, math.sin(hy), math.cos(hy)]
    q_pitch = [0.0, math.sin(hp), 0.0, math.cos(hp)]
    return quat_mul(q_yaw, q_pitch)


# --------------------------------------------------------------------------
# Args.
# --------------------------------------------------------------------------
def _finite(value, label):
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|%r" % (label, value))
    return number


def check_args(args):
    """Normalise the args json; APPLY/REVERT need confirm '<MODE> P01RIGPATTERN'."""
    args = dict(args or {})
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    target = args.get("target_passage", PASSAGE_KEY)
    template_passage = args.get("template_passage", PASSAGE_KEY)
    cfg = passage_config(target)
    passage_config(template_passage)
    token = cfg["confirm_token"]
    if mode != "DRY":
        require(args.get("confirm") == "%s %s" % (mode, token),
                "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, token))
    p01 = target == PASSAGE_KEY
    jitter = dict(DEFAULT_JITTER)
    jitter.update(args.get("jitter") or {})
    loc = _finite(jitter["loc_cm"], "JITTER_LOC")
    rot = _finite(jitter["rot_deg"], "JITTER_ROT")
    require(0.0 <= loc <= 200.0 and 0.0 <= rot <= 45.0, "JITTER_RANGE|loc_cm=%s|rot_deg=%s" % (loc, rot))
    seed = jitter["seed"]
    require(isinstance(seed, int) and not isinstance(seed, bool), "JITTER_SEED_NOT_INT|%r" % (seed,))
    roles = args.get("roles", list(DEFAULT_ROLES))
    require(isinstance(roles, list) and roles and all(isinstance(r, str) and r for r in roles)
            and len(set(roles)) == len(roles), "ROLES_INVALID|%r" % (roles,))
    # P01-specific defaults (B05 beam skip, B01/B02 exclusion) only apply when the target is P01.
    skip = args.get("skip", [list(s) for s in DEFAULT_SKIP] if p01 else [])
    require(isinstance(skip, list) and all(isinstance(s, (list, tuple)) and len(s) == 2
                                           and all(isinstance(x, str) for x in s) for s in skip),
            "SKIP_INVALID|%r" % (skip,))
    # "template_cues" (7 Oct name) and "templates" (6 Oct name, kept for the P01 args/record) are aliases.
    given = [args[k] for k in ("templates", "template_cues") if k in args]
    require(len(given) < 2 or dict(given[0]) == dict(given[1]), "TEMPLATE_CUES_CONFLICT|%r" % (given,))
    templates = dict(given[0] if given else DEFAULT_TEMPLATES)
    require(set(templates) == {"-", "+"} and templates["-"] != templates["+"], "TEMPLATES_INVALID|%r" % templates)
    require(all(str(v).startswith(template_passage + " ") for v in templates.values()),
            "TEMPLATE_CUE_NOT_IN_TEMPLATE_PASSAGE|passage=%s|%r" % (template_passage, templates))
    exclude = list(args.get("exclude_cues", list(DEFAULT_EXCLUDE) if p01 else []))
    expected = args.get("expected_targets")
    require(expected is None or (isinstance(expected, int) and not isinstance(expected, bool)),
            "EXPECTED_TARGETS_INVALID|%r" % (expected,))
    no_parity = args.get("no_parity_template")
    require(no_parity in (None, "-", "+"), "NO_PARITY_TEMPLATE_INVALID|%r" % (no_parity,))
    require(not (p01 and no_parity is not None), "NO_PARITY_TEMPLATE_NOT_FOR_P01")
    scale = args.get("intensity_scale")
    if scale is not None:
        require(not p01, "INTENSITY_SCALE_NOT_FOR_P01")
        require(not isinstance(scale, bool), "INTENSITY_SCALE_INVALID|%r" % (scale,))
        scale = _finite(scale, "INTENSITY_SCALE")
        require(0.0 < scale <= INTENSITY_SCALE_MAX, "INTENSITY_SCALE_RANGE|%s" % scale)
    shadows = args.get("cast_shadows")
    require(shadows in (None, True), "CAST_SHADOWS_INVALID|%r (only true or null)" % (shadows,))
    require(not (p01 and shadows), "CAST_SHADOWS_NOT_FOR_P01")
    protected = args.get("protected_cue_guids", []) or []
    require(isinstance(protected, list) and all(isinstance(g, str) and len(g) == 32 for g in protected),
            "PROTECTED_CUE_GUIDS_INVALID|%r" % (protected,))
    require(not (p01 and protected), "PROTECTED_CUE_GUIDS_NOT_FOR_P01")
    allow_dirty = list(args.get("allow_dirty", []) or [])
    out = {"mode": mode, "confirm": args.get("confirm"),
           "jitter": {"loc_cm": loc, "rot_deg": rot, "seed": seed},
           "roles": list(roles), "skip": [list(s) for s in skip], "templates": templates,
           "exclude_cues": exclude, "expected_targets": expected,
           "ack_records": list(args.get("ack_records", []) or []), "allow_dirty": allow_dirty,
           "target_passage": target, "template_passage": template_passage}
    if not p01:
        # Parity fallback (LOW_SIDE_R_FILL inverted, then BEAM_R) and the optional template for bays with no
        # parity role exist only off P01, so a P01 plan is identical to the one applied on 6 Oct.
        out.update({"parity_fallback": True, "no_parity_template": no_parity, "intensity_scale": scale,
                    "cast_shadows": bool(shadows), "protected_cue_guids": sorted(g.upper() for g in protected)})
    return out


# --------------------------------------------------------------------------
# Plan (pure).
# --------------------------------------------------------------------------
def base_role(role):
    return role[:-len("_BODY")] if role.endswith("_BODY") else role


def jitter_value(seed, cue_label, role, axis, amplitude):
    """One separately seeded generator per number (never two draws in one expression)."""
    if amplitude == 0.0:
        return 0.0
    rng = random.Random("%s|%s|%s|%s" % (seed, cue_label, role, axis))
    value = rng.uniform(-amplitude, amplitude)
    return value


def jitter_for(jitter, cue_label, role):
    key = base_role(role)   # the light and its _BODY prop share every offset
    out = {}
    for axis in ("dx", "dy", "dz"):
        out[axis] = jitter_value(jitter["seed"], cue_label, key, axis, jitter["loc_cm"])
    for axis in ("yaw", "pitch"):
        out[axis] = jitter_value(jitter["seed"], cue_label, key, axis, jitter["rot_deg"])
    return out


def score_roles(cue, pattern=SCORE_LABEL):
    """{role: (attachment_index, row)} for the cue's <passage> SCORE rows; duplicate roles stop."""
    out, bays = {}, set()
    for index, row in enumerate(cue["attachments"]):
        match = pattern.match(str(row["label"]))
        if not match:
            continue
        bays.add(match.group(1))
        role = match.group(2)
        require(role not in out, "DUPLICATE_ROLE|cue=%s|role=%s" % (cue["label"], role))
        out[role] = (index, row)
    require(len(bays) <= 1, "MIXED_BAY_TOKENS|cue=%s|%s" % (cue["label"], sorted(bays)))
    return out, (sorted(bays)[0] if bays else None)


def parity_of(roles, cue_label):
    if PARITY_ROLE not in roles:
        return None
    y = float(roles[PARITY_ROLE][1]["relative_transform"]["location"][1])
    require(y != 0.0, "PARITY_ZERO|cue=" + cue_label)
    return "-" if y < 0.0 else "+"


def parity_with_fallback(roles, cue_label):
    """(parity, source_role): LOW_SIDE_L_KEY sign; else LOW_SIDE_R_FILL sign inverted; else BEAM_R sign.

    (None, None) when the bay has none of the three. Off-P01 targets only."""
    for role, factor in PARITY_FALLBACK:
        if role in roles:
            y = float(roles[role][1]["relative_transform"]["location"][1]) * factor
            require(y != 0.0, "PARITY_ZERO|cue=%s|role=%s" % (cue_label, role))
            return ("-" if y < 0.0 else "+"), role
    return None, None


def panel_abs_y(aims, y):
    """|target_cm y| of this bay's aim on the same side as y (lighting_scores_record aims); None if unknown."""
    side = [abs(float(a["target_cm"][1])) for a in (aims or [])
            if float(a["target_cm"][1]) != 0.0 and (float(a["target_cm"][1]) < 0.0) == (y < 0.0)]
    return min(side) if side else None


def build_plan(plain, options, aims_by_cue=None):
    opts = options
    aims_by_cue = aims_by_cue or {}
    cues = plain["cues"]
    guids = [c["guid"] for c in cues]
    require(len(guids) == len(set(guids)), "DUPLICATE_CUE_GUID")
    by_guid = {c["guid"]: c for c in cues}
    bay_guids = list(plain["bay_guids"])
    require(bay_guids, "NO_P01_BAYS")
    missing = [g for g in bay_guids if g not in by_guid]
    require(not missing, "BAY_GUID_UNRESOLVED|%s" % missing)
    target_key = opts.get("target_passage", PASSAGE_KEY)
    template_key = opts.get("template_passage", PASSAGE_KEY)
    target_cfg, template_cfg = passage_config(target_key), passage_config(template_key)
    fallback = bool(opts.get("parity_fallback")) and target_key != PASSAGE_KEY
    no_parity_template = opts.get("no_parity_template") if fallback else None
    intensity_scale = opts.get("intensity_scale") if fallback else None
    cast_shadows = bool(opts.get("cast_shadows")) if fallback else False
    protected = set(opts.get("protected_cue_guids") or []) if fallback else set()
    bays = sorted((by_guid[g] for g in bay_guids), key=lambda c: c["show_index"])
    wrong = [c["label"] for c in bays if not str(c["label"]).startswith(target_key + " ")]
    require(not wrong, "BAY_NOT_%s|%s" % (target_key, wrong))
    all_att = [row["guid"] for c in cues for row in c["attachments"]]

    # Templates, read live, parity asserted (strict LOW_SIDE_L_KEY parity, never the fallback).
    if template_key == target_key:
        template_pool = bays
    else:
        pool_guids = plain.get("template_bay_guids")
        template_pool = ([by_guid[g] for g in pool_guids if g in by_guid] if pool_guids is not None else cues)
    templates = {}
    for sign in ("-", "+"):
        label = opts["templates"][sign]
        hits = [c for c in template_pool if c["label"] == label]
        require(len(hits) == 1, "TEMPLATE_CUE_COUNT|label=%s|count=%d" % (label, len(hits)))
        require(hits[0]["guid"] not in bay_guids or template_key == target_key,
                "TEMPLATE_IS_TARGET|label=" + label)
        roles, bay_token = score_roles(hits[0], template_cfg["score_label"])
        parity = parity_of(roles, label)
        require(parity == sign, "TEMPLATE_PARITY_WRONG|cue=%s|expected=%s|live=%s" % (label, sign, parity))
        templates[sign] = {"cue_label": label, "cue_guid": hits[0]["guid"], "bay_token": bay_token,
                           "roles": {role: {"location": list(row["relative_transform"]["location"]),
                                            "rotation_xyzw": canonical_quat(row["relative_transform"]["rotation_xyzw"]),
                                            "kind": _enum_name(row["kind"]), "anchor": _enum_name(row["anchor"]),
                                            "guid": row["guid"], "label": row["label"]}
                                     for role, (unused, row) in roles.items()}}

    template_labels = {t["cue_label"] for t in templates.values()}
    skip = {(s[0], s[1]) for s in opts["skip"]}
    jitter = opts["jitter"]
    targets, untouched, skipped, no_template, warnings, bay_rows = [], [], [], [], [], []
    role_counts = {role: {"present": 0, "moved": 0, "skipped": 0} for role in opts["roles"]}
    for cue in bays:
        roles, bay_token = score_roles(cue, target_cfg["score_label"])
        parity_source = PARITY_ROLE
        if fallback:
            parity, parity_source = parity_with_fallback(roles, cue["label"])
        else:
            parity = parity_of(roles, cue["label"])
        planned_roles = [r for r in opts["roles"] if r in roles]
        info = {"cue_label": cue["label"], "cue_guid": cue["guid"], "show_index": cue["show_index"],
                "bay_token": bay_token, "parity": parity, "rows": []}
        if fallback:
            info["parity_source"] = parity_source
        if cue["label"] in template_labels:
            info["status"] = "TEMPLATE"
        elif str(cue["guid"]).upper() in protected:
            info["status"] = "PROTECTED"
        elif cue["label"] in opts["exclude_cues"]:
            info["status"] = "EXCLUDED"
        elif not roles:
            info["status"] = "NO_SCORE_ROWS"
        elif parity is None and fallback and planned_roles and no_parity_template is not None:
            parity, info["parity"], info["parity_source"] = no_parity_template, no_parity_template, "NO_PARITY_TEMPLATE"
            info["status"] = "TARGET"
            warnings.append("NO_PARITY_TEMPLATE_USED|cue=%s|template=%s|roles=%s"
                            % (cue["label"], no_parity_template, ",".join(planned_roles)))
        elif parity is None and fallback and planned_roles:
            info["status"] = "NO_PARITY"
            warnings.append("NO_PARITY|cue=%s|roles=%s" % (cue["label"], ",".join(planned_roles)))
        elif parity is None:
            info["status"] = "PRACTICAL_ONLY"
        else:
            info["status"] = "TARGET"
        if fallback and parity_source not in (None, PARITY_ROLE, "NO_PARITY_TEMPLATE"):
            warnings.append("PARITY_FALLBACK|cue=%s|via=%s|parity=%s" % (cue["label"], parity_source, parity))
        if fallback and PARITY_ROLE in roles and "LOW_SIDE_R_FILL" in roles:
            key_y = float(roles[PARITY_ROLE][1]["relative_transform"]["location"][1])
            fill_y = float(roles["LOW_SIDE_R_FILL"][1]["relative_transform"]["location"][1])
            if (key_y < 0.0) == (fill_y < 0.0):
                warnings.append("SIDE_PARITY_CONFLICT|cue=%s|key_y=%.1f|fill_y=%.1f" % (cue["label"], key_y, fill_y))
        if info["status"] != "TARGET":
            untouched.append({k: info[k] for k in ("cue_label", "status", "bay_token", "parity")})
            bay_rows.append(info)
            continue
        template = templates[parity]
        info["missing_roles"] = [r for r in opts["roles"] if r not in roles and r in template["roles"]]
        for r in planned_roles:
            role_counts[r]["present"] += 1
        beam = roles.get("BEAM_R")
        if beam is not None:
            beam_sign = "-" if float(beam[1]["relative_transform"]["location"][1]) < 0.0 else "+"
            if beam_sign != parity:
                warnings.append("BEAM_PARITY_MISMATCH|cue=%s|parity=%s|beam=%s" % (cue["label"], parity, beam_sign))
        for role in opts["roles"]:
            if role not in roles:
                continue
            index, row = roles[role]
            if (cue["label"], role) in skip or (cue["label"], "*") in skip:
                skipped.append({"cue_label": cue["label"], "role": role, "guid": row["guid"]})
                role_counts[role]["skipped"] += 1
                continue
            src = template["roles"].get(role)
            if src is None:
                no_template.append({"cue_label": cue["label"], "role": role, "parity": parity})
                continue
            require(all_att.count(row["guid"]) == 1, "TARGET_GUID_NOT_UNIQUE|guid=" + row["guid"])
            if fallback:
                require(target_cfg["score_label"].match(str(row["label"]))
                        and not FORBIDDEN_TARGET_LABEL.search(str(row["label"])),
                        "FORBIDDEN_TARGET_LABEL|cue=%s|label=%s" % (cue["label"], row["label"]))
            require(_enum_name(row["kind"]) == src["kind"], "KIND_MISMATCH|cue=%s|role=%s|%s!=%s"
                    % (cue["label"], role, _enum_name(row["kind"]), src["kind"]))
            require(_enum_name(row["anchor"]) == src["anchor"], "ANCHOR_MISMATCH|cue=%s|role=%s|%s!=%s"
                    % (cue["label"], role, _enum_name(row["anchor"]), src["anchor"]))
            j = jitter_for(jitter, cue["label"], role)
            if jitter["loc_cm"] == 0.0:
                loc_after = list(src["location"])
            else:
                loc_after = [src["location"][0] + j["dx"], src["location"][1] + j["dy"], src["location"][2] + j["dz"]]
            if jitter["rot_deg"] == 0.0:
                rot_after = list(src["rotation_xyzw"])
            else:
                rot_after = canonical_quat(quat_mul(src["rotation_xyzw"], delta_quat(j["yaw"], j["pitch"])))
            before = row["relative_transform"]
            panel = panel_abs_y(aims_by_cue.get(cue["guid"]), loc_after[1])
            inside = panel is not None and abs(loc_after[1]) < panel
            target = {
                "cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue["show_index"],
                "bay_token": bay_token, "role": role, "attachment_guid": row["guid"],
                "attachment_label": row["label"], "attachment_index": index, "kind": src["kind"],
                "enabled": bool(row.get("enabled", True)), "parity": parity,
                "template_cue": template["cue_label"], "template_guid": src["guid"],
                "location_before": list(before["location"]),
                "rotation_before": canonical_quat(before["rotation_xyzw"]),
                "location_after": loc_after, "rotation_after": rot_after, "jitter": j,
                "abs_y_before": abs(float(before["location"][1])), "abs_y_after": abs(loc_after[1]),
                "z_before": float(before["location"][2]), "z_after": loc_after[2],
                "panel_abs_y": panel, "inside_panel_band": inside,
                "unchanged": (list(before["location"]) == loc_after
                              and quat_close(before["rotation_xyzw"], rot_after, 0.0)),
            }
            if intensity_scale is not None and src["kind"] == "LIGHT":
                before_i = _finite(row["lighting"]["intensity"], "INTENSITY_BEFORE")
                target["intensity_before"] = before_i
                target["intensity_after"] = f32(before_i * intensity_scale)
                target["unchanged"] = target["unchanged"] and target["intensity_after"] == before_i
            if cast_shadows and src["kind"] == "LIGHT" and base_role(role) in SHADOW_ROLES:
                before_s = row["lighting"]["cast_shadows"]
                require(isinstance(before_s, bool), "CAST_SHADOWS_NOT_BOOL|guid=%s|%r" % (row["guid"], before_s))
                target["cast_shadows_before"] = before_s
                target["cast_shadows_after"] = True
                target["unchanged"] = target["unchanged"] and before_s is True
            if inside and src["kind"] == "LIGHT":
                warnings.append("PANEL_BAND|cue=%s|role=%s|abs_y=%.1f|panel=%.1f"
                                % (cue["label"], role, abs(loc_after[1]), panel))
            targets.append(target)
            role_counts[role]["moved"] += 1
            info["rows"].append({"role": role, "abs_y": [round(target["abs_y_before"], 1), round(target["abs_y_after"], 1)],
                                 "z": [round(target["z_before"], 1), round(target["z_after"], 1)],
                                 "inside_panel_band": inside})
        bay_rows.append(info)

    require(targets, "ZERO_TARGETS")
    expected = opts.get("expected_targets")
    if expected is not None:
        require(int(expected) == len(targets), "EXPECTED_TARGETS|expected=%s|planned=%d" % (expected, len(targets)))
    targets.sort(key=lambda t: (t["show_index"], t["attachment_index"]))
    return {
        "passage": target_key, "template_passage": template_key, "parity_fallback": fallback,
        "no_parity_template": no_parity_template, "role_counts": role_counts, "intensity_scale": intensity_scale,
        "intensity_guids": sorted(t["attachment_guid"] for t in targets if "intensity_after" in t),
        "cast_shadows": cast_shadows, "protected_cue_guids": sorted(protected),
        "shadow_guids": sorted(t["attachment_guid"] for t in targets if "cast_shadows_after" in t),
        "roles": list(opts["roles"]), "jitter": dict(jitter),
        "skip": [list(s) for s in sorted(skip)], "exclude_cues": list(opts["exclude_cues"]),
        "templates": templates, "targets": targets,
        "target_cue_guids": sorted({t["cue_guid"] for t in targets}),
        "target_attachment_guids": sorted({t["attachment_guid"] for t in targets}),
        "target_bays": sorted({t["cue_label"] for t in targets}),
        "untouched_bays": untouched, "skipped": skipped, "no_template": no_template,
        "warnings": warnings, "bays": bay_rows, "bay_count": len(bays),
    }


# --------------------------------------------------------------------------
# Scope guards, offline mutation model, revert model.
# --------------------------------------------------------------------------
def f32(value):
    """Round to the float32 the Show stores (FInfinityStageLightSettings::Intensity, InfinityStageTypes.h:204)."""
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def intensity_close(a, b):
    a, b = float(a), float(b)
    return abs(a - b) <= INTENSITY_REL_TOL * max(abs(a), abs(b), 1.0e-3)


def plan_intensity_guids(plan):
    return list(plan.get("intensity_guids") or [])


def field_close(field, a, b):
    return intensity_close(a, b) if field == "intensity" else a == b


def row_fields(plan, guid):
    """Lighting fields the plan writes on this attachment (from older records: none)."""
    return tuple(f for f, key, unused, unused2 in LIGHTING_FIELDS if guid in set(plan.get(key) or []))


def plan_field_guids(plan):
    return {f: list(plan.get(key) or []) for f, key, unused, unused2 in LIGHTING_FIELDS}


def _side_values(target, side):
    require(side in ("before", "after"), "SIDE_INVALID|" + str(side))
    return target["location_" + side], target["rotation_" + side]


def expected_rows(rows, plan, side):
    out = copy.deepcopy(rows)
    by_guid = {t["attachment_guid"]: t for t in plan["targets"]}
    for row in out:
        target = by_guid.get(row["guid"])
        if target is not None:
            loc, rot = _side_values(target, side)
            row["relative_transform"]["location"] = list(loc)
            row["relative_transform"]["rotation_xyzw"] = list(rot)
            for field, unused, unused2, unused3 in LIGHTING_FIELDS:
                if field + "_" + side in target:
                    row["lighting"][field] = target[field + "_" + side]
    return out


def apply_plain(all_rows, plan, side="after"):
    result = copy.deepcopy(all_rows)
    for cue_guid in plan["target_cue_guids"]:
        result[cue_guid] = expected_rows(all_rows[cue_guid], plan, side)
    return result


def row_differences(tool, want, got, written, fields=()):
    """Exact field differences, except a written row's location/rotation (tolerance; q ~ -q) and the lighting
    fields the plan writes on it (intensity: float32 relative tolerance; cast_shadows: exact)."""
    if not written:
        return tool._state_differences(want, got)
    a, b = copy.deepcopy(want), copy.deepcopy(got)
    out = []
    for field in fields:
        va, vb = a["lighting"].pop(field), b["lighting"].pop(field)
        if not field_close(field, va, vb):
            out.append({"path": "lighting." + field, "before": va, "after": vb})
    la, lb = a["relative_transform"].pop("location"), b["relative_transform"].pop("location")
    ra, rb = a["relative_transform"].pop("rotation_xyzw"), b["relative_transform"].pop("rotation_xyzw")
    if len(la) != 3 or len(lb) != 3 or max(abs(float(x) - float(y)) for x, y in zip(la, lb)) > LOC_TOL_CM:
        out.append({"path": "relative_transform.location", "before": la, "after": lb})
    if len(ra) != 4 or len(rb) != 4 or not quat_close(ra, rb):
        out.append({"path": "relative_transform.rotation_xyzw", "before": ra, "after": rb})
    return out + tool._state_differences(a, b)


def scope_differences(tool, base_all, live_all, plan, side):
    """[] iff live == base with exactly the targets' location/rotation set to plan[side]."""
    problems = []
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    if tool._outside_hash(base_all, plan["target_cue_guids"]) != tool._outside_hash(live_all, plan["target_cue_guids"]):
        problems.append({"cue": "*", "problem": "OUTSIDE_TARGET_SCOPE_CHANGED"})
    targets = set(plan["target_attachment_guids"])
    for cue_guid in plan["target_cue_guids"]:
        want, got = expected_rows(base_all[cue_guid], plan, side), live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in got]:
            problems.append({"cue": cue_guid, "problem": "ROW_SET_OR_ORDER_CHANGED"})
            continue
        for w, g in zip(want, got):
            diffs = row_differences(tool, w, g, w["guid"] in targets, row_fields(plan, w["guid"]))
            if diffs:
                problems.append({"cue": cue_guid, "guid": w["guid"], "label": w["label"], "differences": diffs})
    return problems


def check_scope(tool, base_all, live_all, plan, side):
    problems = scope_differences(tool, base_all, live_all, plan, side)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), _canonical(problems)[:3000]))


def target_rows(all_rows, plan):
    out = {}
    for target in plan["targets"]:
        rows = all_rows.get(target["cue_guid"])
        require(rows is not None, "TARGET_CUE_GONE|" + target["cue_guid"])
        hits = [row for row in rows if row["guid"] == target["attachment_guid"]]
        require(len(hits) == 1, "TARGET_ROW_RESOLVE|guid=" + target["attachment_guid"])
        out[target["attachment_guid"]] = copy.deepcopy(hits[0])
    return out


def revert_drifts(all_rows, record):
    """ALL touched fields whose live value != the record's after (not just the first)."""
    drifts = []
    for target in record["plan"]["targets"]:
        rows = all_rows.get(target["cue_guid"]) or []
        hits = [row for row in rows if row["guid"] == target["attachment_guid"]]
        if len(hits) != 1:
            drifts.append({"guid": target["attachment_guid"], "label": target["attachment_label"],
                           "field": "<row>", "live": "count=%d" % len(hits)})
            continue
        live = hits[0]["relative_transform"]
        loc, rot = target["location_after"], target["rotation_after"]
        if max(abs(float(x) - float(y)) for x, y in zip(live["location"], loc)) > LOC_TOL_CM:
            drifts.append({"guid": target["attachment_guid"], "label": target["attachment_label"],
                           "field": "relative_transform.location", "record_after": loc, "live": live["location"]})
        if not quat_close(live["rotation_xyzw"], rot):
            drifts.append({"guid": target["attachment_guid"], "label": target["attachment_label"],
                           "field": "relative_transform.rotation_xyzw", "record_after": rot,
                           "live": live["rotation_xyzw"]})
        for field, unused, unused2, unused3 in LIGHTING_FIELDS:
            if field + "_after" in target and not field_close(field, hits[0]["lighting"][field], target[field + "_after"]):
                drifts.append({"guid": target["attachment_guid"], "label": target["attachment_label"],
                               "field": "lighting." + field, "record_after": target[field + "_after"],
                               "live": hits[0]["lighting"][field]})
    return drifts


def check_revert_drift(all_rows, record):
    drifts = revert_drifts(all_rows, record)
    require(not drifts, "REVERT_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:4000]))


def revert_plain(tool, all_rows, record):
    check_revert_drift(all_rows, record)
    result = apply_plain(all_rows, record["plan"], "before")
    restored = target_rows(result, record["plan"])
    before = record["before_target_rows"]
    for guid, row in restored.items():
        fields = row_fields(record["plan"], guid)
        diffs = [d for d in row_differences(tool, before[guid], row, True, fields)]
        # Only location/rotation (and written lighting fields) are restored; other fields keep any later hand value.
        restored_paths = ("relative_transform.location", "relative_transform.rotation_xyzw") + tuple(
            "lighting." + f for f in fields)
        diffs = [d for d in diffs if d["path"] in restored_paths]
        require(not diffs, "REVERT_NOT_EXACT|guid=%s|%s" % (guid, _canonical(diffs)))
    return result


def check_record(record, passage=PASSAGE_KEY):
    require(record.get("passage") == passage and record.get("plan", {}).get("passage") == passage,
            "RECORD_PASSAGE_MISMATCH|%s" % record.get("passage"))
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|" + str(record.get("status")))


def readback_rows(read_all, plan, side):
    """Per-row assertion list for the report."""
    rows = target_rows(read_all, plan)
    out = []
    for target in plan["targets"]:
        live = rows[target["attachment_guid"]]["relative_transform"]
        loc, rot = _side_values(target, side)
        ok = (max(abs(float(x) - float(y)) for x, y in zip(live["location"], loc)) <= LOC_TOL_CM
              and quat_close(live["rotation_xyzw"], rot))
        for field, unused, unused2, unused3 in LIGHTING_FIELDS:
            if field + "_" + side in target:
                ok = ok and field_close(field, rows[target["attachment_guid"]]["lighting"][field],
                                        target[field + "_" + side])
        out.append({"guid": target["attachment_guid"], "label": target["attachment_label"], "ok": ok})
    bad = [r for r in out if not r["ok"]]
    require(not bad, "READBACK_ROWS|side=%s|bad=%d|%s" % (side, len(bad), _canonical(bad)[:2000]))
    return out


# --------------------------------------------------------------------------
# Export-text scope (rig_lamp_drop.py:608-642), masking Rotation + Translation of targets.
# --------------------------------------------------------------------------
_OWN_GUID = re.compile(r"[(,]AttachmentGuid=([0-9A-Fa-f]{32})")
_ROT_OR_TRANS = re.compile(r"(?<![A-Za-z])(Rotation|Translation)=\([^()]*\),?")
_LIGHTING_OPEN = re.compile(r"(?<![A-Za-z])Lighting=\(")
def _mask_intensity(segment, guid, name="Intensity"):
    """Mask the one top-level <name>= inside the segment's Lighting=(..) group (nested groups untouched)."""
    pattern = re.compile(r"(?<![A-Za-z])%s=[^,()]*,?" % re.escape(name))
    found = list(_LIGHTING_OPEN.finditer(segment))
    require(len(found) >= 1, "EXPORT_NO_LIGHTING|guid=" + guid)
    open_at = found[0].end() - 1
    close_at = _close_paren(segment, open_at)
    inner = segment[open_at + 1:close_at]
    hits = [m for m in pattern.finditer(inner)
            if inner[:m.start()].count("(") == inner[:m.start()].count(")")]
    # ExportText omits a field equal to its default (bCastShadows defaults true, InfinityStageTypes.h:239; measured
    # 7 Oct: P06 DRY found count=0), so 0 or 1 hit is valid; the field is REMOVED (not placeholdered) so a before text
    # without it and an after text with it normalise to the same string.
    require(len(hits) <= 1, "EXPORT_%s_COUNT|guid=%s|count=%d" % (name.upper(), guid, len(hits)))
    if not hits:
        return segment
    m = hits[0]
    return segment[:open_at + 1] + inner[:m.start()] + inner[m.end():] + segment[close_at:]


def _close_paren(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise P01RigPatternError("EXPORT_UNBALANCED")


def normalize_export(texts, target_guids, intensity_guids=(), shadow_guids=()):
    wanted = {g.upper() for g in target_guids}
    scaled = {g.upper() for g in intensity_guids}
    shadowed = {g.upper() for g in shadow_guids}
    require(scaled <= wanted, "EXPORT_INTENSITY_NOT_TARGET")
    require(shadowed <= wanted, "EXPORT_SHADOWS_NOT_TARGET")
    seen = {g: 0 for g in wanted}
    out = []
    for text in texts:
        marks = list(_OWN_GUID.finditer(text))
        pieces, cursor = [], 0
        for index, match in enumerate(marks):
            guid = match.group(1).upper()
            if guid not in wanted:
                continue
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            segment = text[match.start():end]
            anchor = segment.find("RelativeTransform=(")
            require(anchor >= 0, "EXPORT_NO_RELATIVE_TRANSFORM|guid=" + guid)
            open_at = match.start() + anchor + len("RelativeTransform=")
            close_at = _close_paren(text, open_at)
            inner = text[open_at + 1:close_at]
            masked = _ROT_OR_TRANS.sub("", inner)
            pieces.append(text[cursor:open_at + 1])
            pieces.append("<RT>" + masked)
            cursor = close_at
            if guid in scaled or guid in shadowed:
                # the rest of this attachment's segment with the written lighting fields masked
                rest = text[close_at:end]
                if guid in scaled:
                    rest = _mask_intensity(rest, guid, "Intensity")
                if guid in shadowed:
                    rest = _mask_intensity(rest, guid, "bCastShadows")
                pieces.append(rest)
                cursor = end
            seen[guid] += 1
        pieces.append(text[cursor:])
        out.append("".join(pieces))
    require(all(count == 1 for count in seen.values()), "EXPORT_TARGET_COUNT|%s"
            % _canonical({g: c for g, c in seen.items() if c != 1}))
    return out


def export_hash(texts, target_guids, intensity_guids=(), shadow_guids=()):
    return _sha256_text("\n".join(normalize_export(texts, target_guids, intensity_guids, shadow_guids)))


# --------------------------------------------------------------------------
# Context gate (pure), rig_lamp_drop.py:645.
# --------------------------------------------------------------------------
def check_context(ctx, mode, allow_dirty=(), show_path=None, world_path=None):
    require(ctx.get("project_ok", True), "WRONG_PROJECT")
    require(ctx.get("world_ok", True), "WRONG_WORLD|" + str(ctx.get("world")))
    census = ctx.get("census") or {}
    if mode == "DRY":
        return
    require(not ctx.get("pie"), "PIE_OR_SIE_ACTIVE")
    require(not ctx.get("sequencer_open"), "SEQUENCER_IS_OPEN")
    require(not ctx.get("zz_actors"), "STRAY_ZZ_ACTORS|" + ",".join(ctx.get("zz_actors") or []))
    allowed = set(allow_dirty or [])
    if show_path or world_path:
        require(allowed <= {show_path, world_path}, "ALLOW_DIRTY_OUT_OF_SCOPE|%s" % sorted(allowed))
    dirty = set(census.get("content") or []) | set(census.get("maps") or [])
    require(dirty <= allowed, "DIRTY_BEFORE|census=" + _canonical(census))


def check_apply_gate(unacked, record_file=RECORD_PATH):
    require(not os.path.exists(record_file), "ACTIVE_RECORD_EXISTS|" + record_file)
    require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))


def load_protected(path):
    """plan.yield_to_events.cue_guids of a scores record (P06 BLACK-mode bays); refuses if absent or empty."""
    require(os.path.isfile(path), "PROTECTED_SOURCE_MISSING|" + path)
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    guids = ((record.get("plan") or {}).get("yield_to_events") or {}).get("cue_guids") or []
    require(guids and all(isinstance(g, str) and len(g) == 32 for g in guids), "PROTECTED_SOURCE_EMPTY|" + path)
    return [g.upper() for g in guids]


def load_aims(path=SCORES_RECORD_P01):
    """{cue_guid: aims} from the P01 scores record (panel |y| for the advisory PANEL warning)."""
    if not os.path.isfile(path):
        return {}, None
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    plan = record.get("plan") or {}
    return ({t["cue_guid"]: t.get("aims") or [] for t in plan.get("targets", [])},
            plan.get("passage_guid"))


# --------------------------------------------------------------------------
# Module loading (lighting_scores_apply.py, then its load_p04_tool()) — rig_lamp_drop.py:682-749.
# --------------------------------------------------------------------------
_SAFE_CALLS = {"os.path.join", "os.path.dirname", "os.path.abspath", "os.path.normcase",
               "os.path.normpath", "re.compile", "tuple", "frozenset", "set", "dict", "list",
               "_load_attachment_state"}


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
            and node.test.left.id == "unreal" and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main"
            and not node.body[0].value.args and not node.body[0].value.keywords)


def _top_level_ok(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Expr):
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value is None or all(_dotted(c.func) in _SAFE_CALLS
                                         for c in ast.walk(node.value) if isinstance(c, ast.Call))
    if isinstance(node, ast.Try):
        inner = list(node.body) + [s for h in node.handlers for s in h.body] + list(node.orelse) + list(node.finalbody)
        return all(isinstance(s, (ast.Import, ast.ImportFrom))
                   or (isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)) for s in inner)
    return False


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if _is_main_guard(n)) == 1, "MAIN_GUARD_SHAPE|" + path)
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_ok(node, index), "TOP_LEVEL_SIDE_EFFECT|%s|line=%d" % (path, getattr(node, "lineno", -1)))
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


SCORES_REQUIRED = ("load_p04_tool", "_materialize_passage", "_count_passage_actors", "scan_foreign_records")
TOOL_EXTRA_REQUIRED = ("S", "_state_differences", "_outside_hash", "_guid_text", "_write_json", "_read_json",
                       "_dirty_census", "_backup", "_save_narrow", "_pair_attachments", "_set_pair_attachments",
                       "_attachment_rows", "SHOW_PATH", "EXPECTED_WORLD", "EXPECTED_PROJECT", "_asset_id")


def load_modules():
    scores = load_without_main(SCORES_TOOL_PATH, "_lighting_scores_for_p01_rig_pattern")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()
    missing = [n for n in TOOL_EXTRA_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


def scan_foreign(scores, plan, saved_dir=None, record_path=RECORD_PATH):
    saved = saved_dir or os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, plan["target_attachment_guids"], exclude=[record_path])


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _ctx_facts(tool):
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))).rstrip("\\/")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world is not None else []
    return {"project_ok": project == tool.EXPECTED_PROJECT.rstrip("\\/"),
            "world": tool._asset_id(world) if world is not None else None,
            "world_ok": world is not None and tool._asset_id(world) == tool.EXPECTED_WORLD,
            "pie": editor.get_game_world() is not None,
            "sequencer_open": library is not None and library.get_current_level_sequence() is not None,
            "census": tool._dirty_census(),
            "zz_actors": sorted(a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_"))}


def _bay_guids(tool, show, record_passage_guid, passage_label=PASSAGE_LABEL):
    rows = [s for s in show.get_editor_property("passage_settings")
            if str(s.get_editor_property("label")) == passage_label]
    require(len(rows) == 1, "PASSAGE_ROW_COUNT|label=%s|count=%d" % (passage_label, len(rows)))
    guid_value = rows[0].get_editor_property("passage_guid")
    guid = tool._guid_text(guid_value)
    if record_passage_guid:
        require(guid == record_passage_guid, "PASSAGE_GUID_DRIFT|live=%s|record=%s" % (guid, record_passage_guid))
    return guid, [tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(guid_value)]


def _runtime_plain(tool, show, record_passage_guid, cfg=None, template=None):
    """template: None (templates inside the target passage) or (template_cfg, template_record_passage_guid)."""
    cfg = cfg or passage_config(PASSAGE_KEY)
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")),
                     "attachments": tool._attachment_rows(tool._pair_attachments(cue))})
    passage_guid, bays = _bay_guids(tool, show, record_passage_guid, cfg["label"])
    plain = {"cues": cues, "bay_guids": bays, "passage_guid": passage_guid}
    if template is not None:
        template_guid, template_bays = _bay_guids(tool, show, template[1], template[0]["label"])
        plain.update({"template_bay_guids": template_bays, "template_passage_guid": template_guid})
    return plain


def _all_rows(plain):
    return {cue["guid"]: cue["attachments"] for cue in plain["cues"]}


def _export_texts(show):
    texts = []
    for value in list(show.get_editor_property("cues")) + list(show.get_editor_property("passage_settings")):
        exporter = getattr(value, "export_text", None)
        require(callable(exporter), "EXPORT_TEXT_MISSING|" + type(value).__name__)
        texts.append(str(exporter()))
    return texts


def _write_transforms(tool, show, plan, side, check_side=None):
    """Set each target's relative Translation and Rotation to plan[side]; scale and all else untouched."""
    cues = list(show.get_editor_property("cues"))
    by_cue = {}
    for target in plan["targets"]:
        by_cue.setdefault(target["cue_guid"], []).append(target)
    for cue_guid, items in sorted(by_cue.items()):
        matches = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
        require(len(matches) == 1 and matches[0] == items[0]["show_index"], "TARGET_CUE_RESOLVE|cue=" + cue_guid)
        index = matches[0]
        require(str(cues[index].get_editor_property("label")) == items[0]["cue_label"], "TARGET_LABEL_DRIFT|" + cue_guid)
        attachments = tool._pair_attachments(cues[index])
        for item in items:
            hits = [a for a in attachments if tool._guid_text(a.get_editor_property("attachment_guid"))
                    == item["attachment_guid"]]
            require(len(hits) == 1, "TARGET_ATTACHMENT_RESOLVE|guid=" + item["attachment_guid"])
            attachment = hits[0]
            transform = attachment.get_editor_property("relative_transform")
            if check_side is not None:
                state = tool.S._transform_state(transform)
                want_loc, want_rot = _side_values(item, check_side)
                require(max(abs(a - b) for a, b in zip(state["location"], want_loc)) <= LOC_TOL_CM
                        and quat_close(state["rotation_xyzw"], want_rot),
                        "TARGET_POSITION_DRIFT|guid=%s|live=%s" % (item["attachment_guid"], _canonical(state)))
            loc, rot = _side_values(item, side)
            transform.set_editor_property("translation", unreal.Vector(float(loc[0]), float(loc[1]), float(loc[2])))
            transform.set_editor_property("rotation", unreal.Quat(float(rot[0]), float(rot[1]),
                                                                  float(rot[2]), float(rot[3])))
            attachment.set_editor_property("relative_transform", transform)
            written = [(f, ue) for f, unused, unused2, ue in LIGHTING_FIELDS if f + "_" + side in item]
            if written:
                # FInfinityCueAttachment::Lighting (InfinityStageTypes.h:466), set as lighting_looks_apply.py:1509-1511
                lighting = attachment.get_editor_property("lighting")
                for field, ue_name in written:
                    if check_side is not None:
                        live_v = lighting.get_editor_property(ue_name)
                        live_v = float(live_v) if field == "intensity" else bool(live_v)
                        require(field_close(field, live_v, item[field + "_" + check_side]),
                                "TARGET_%s_DRIFT|guid=%s|live=%s" % (field.upper(), item["attachment_guid"], live_v))
                    value = item[field + "_" + side]
                    lighting.set_editor_property(ue_name, float(value) if field == "intensity" else bool(value))
                attachment.set_editor_property("lighting", lighting)
        tool._set_pair_attachments(show, index, attachments)


def _materialize(scores, show, cfg=None):
    cfg = cfg or passage_config(PASSAGE_KEY)
    prefix = cfg["actor_prefix"]
    require(scores._count_passage_actors(show, prefix) == 1, "PASSAGE_ACTOR_COUNT|" + prefix)
    materialized = scores._materialize_passage(show, prefix)
    require(materialized.get("structure") == cfg["structure_label"], "STRUCTURE_NOT_REFIT|%s" % materialized)
    return materialized


def _dry_rows_log(run, plan, mark=MARK):
    MARK = mark  # noqa: N806 - per-passage marker, same format
    for t in plan["targets"]:
        _log("%s_DRY_ROW|run=%s|cue=%s|role=%s|guid=%s|parity=%s|loc=%s->%s|absy=%.1f->%.1f|z=%.1f->%.1f|panel=%s|inside=%d"
             % (MARK, run, t["cue_label"], t["role"], t["attachment_guid"], t["parity"],
                [round(v, 1) for v in t["location_before"]], [round(v, 1) for v in t["location_after"]],
                t["abs_y_before"], t["abs_y_after"], t["z_before"], t["z_after"],
                None if t["panel_abs_y"] is None else round(t["panel_abs_y"], 1), int(t["inside_panel_band"])))
    for w in plan["warnings"]:
        _log("%s_WARNING|run=%s|%s" % (MARK, run, w))


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False}
    tool = None
    cfg = passage_config(args.get("target_passage", PASSAGE_KEY))
    template_key = args.get("template_passage", PASSAGE_KEY)
    MARK = cfg["mark"]  # noqa: N806 - P01 keeps P01RIGPATTERN; P02 -> P02RIGPATTERN, P03 -> P03RIGPATTERN
    RECORD_PATH = cfg["record_path"]  # noqa: N806 - P01 keeps p01_rig_pattern_record.json
    passage = cfg["key"]
    report["passage"] = passage
    try:
        scores, tool = load_modules()
        report["sources"] = {"scores_sha256": scores.SOURCE_SHA256, "p04_tool_sha256": tool.SCORES_SOURCE_SHA256}
        ctx = _ctx_facts(tool)
        report["context"] = ctx
        check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        aims, record_passage_guid = load_aims(cfg["scores_record"])
        if passage in PROTECTED_FROM_SCORES:
            args = dict(args)
            args["protected_cue_guids"] = sorted(set(args.get("protected_cue_guids") or [])
                                                 | set(load_protected(cfg["scores_record"])))
            report["protected_cue_guids"] = args["protected_cue_guids"]
        template = None
        if template_key != passage:
            template_cfg = passage_config(template_key)
            template = (template_cfg, load_aims(template_cfg["scores_record"])[1])
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        plain = _runtime_plain(tool, show, record_passage_guid, cfg, template)
        before_all = _all_rows(plain)

        if mode in ("DRY", "APPLY"):
            plan = build_plan(plain, args, aims)
            check_scope(tool, before_all, apply_plain(before_all, plan, "after"), plan, "after")   # model self-check
            texts_hash = export_hash(_export_texts(show), plan["target_attachment_guids"], plan_intensity_guids(plan),
                        plan.get("shadow_guids") or [])
            foreign = scan_foreign(scores, plan, record_path=RECORD_PATH)
            unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
            report.update({"plan": plan, "passage_guid": plain["passage_guid"], "foreign_records": foreign,
                           "unacknowledged_foreign_records": unacked,
                           "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
            if mode == "DRY":
                _dry_rows_log(run, plan, MARK)
                _log("%s_ROLE_COUNTS|run=%s|target=%s|template=%s|no_parity_bays=%d|%s"
                     % (MARK, run, passage, plan["template_passage"],
                        sum(1 for u in plan["untouched_bays"] if u["status"] == "NO_PARITY"),
                        _canonical(plan["role_counts"])))
                census_after = tool._dirty_census()
                require(census_after == census_before, "DRY_CENSUS_CHANGED|before=%s|after=%s"
                        % (_canonical(census_before), _canonical(census_after)))
                require(tool._outside_hash(_all_rows(_runtime_plain(tool, show, record_passage_guid, cfg, template)), [])
                        == tool._outside_hash(before_all, []), "DRY_SHOW_ROWS_CHANGED")
                report.update({"ok": True, "mutated": False, "census_after": census_after})
                path = report_path(mode, run, passage=passage)
                tool._write_json(path, report)
                _log("%s_DRY_OK|run=%s|bays=%d|rows=%d|skipped=%d|no_template=%d|untouched_bays=%d|warnings=%d"
                     "|panel_band=%d|jitter=%s|foreign=%d|unacked=%d|census_equal=1|mutated=0|report=%s"
                     % (MARK, run, len(plan["target_bays"]), len(plan["targets"]), len(plan["skipped"]),
                        len(plan["no_template"]), len(plan["untouched_bays"]), len(plan["warnings"]),
                        sum(1 for t in plan["targets"] if t["inside_panel_band"]), _canonical(plan["jitter"]),
                        len(foreign), len(unacked), path))
                return report

            check_apply_gate(unacked, RECORD_PATH)
            backup = tool._backup(backup_prefix(passage=passage), run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": passage,
                      "backup": backup, "args": args, "plan": plan,
                      "outside_before_hash": tool._outside_hash(before_all, plan["target_cue_guids"]),
                      "export_hash_before": texts_hash,
                      "before_cue_rows": {g: before_all[g] for g in plan["target_cue_guids"]},
                      "after_cue_rows": {g: expected_rows(before_all[g], plan, "after")
                                         for g in plan["target_cue_guids"]},
                      "before_target_rows": target_rows(before_all, plan),
                      "after_target_rows": target_rows(apply_plain(before_all, plan, "after"), plan),
                      "acknowledged_records": list(args["ack_records"])}
            tool._write_json(RECORD_PATH, record, exclusive=True)   # fsynced before any mutation
            _log("%s_RECORD_WRITTEN|run=%s|path=%s|rows=%d" % (MARK, run, RECORD_PATH, len(plan["targets"])))
            try:
                _write_transforms(tool, show, plan, "after", check_side="before")
                after_all = _all_rows(_runtime_plain(tool, show, record_passage_guid, cfg, template))
                check_scope(tool, before_all, after_all, plan, "after")
                require(export_hash(_export_texts(show), plan["target_attachment_guids"], plan_intensity_guids(plan),
                        plan.get("shadow_guids") or []) == texts_hash,
                        "EXPORT_OUTSIDE_SCOPE_CHANGED")
            except Exception:
                _write_transforms(tool, show, plan, "before")
                restored = _all_rows(_runtime_plain(tool, show, record_passage_guid, cfg, template))
                check_scope(tool, before_all, restored, plan, "before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            record["status"] = "mutated_verified"
            tool._write_json(RECORD_PATH, record)
            materialized = _materialize(scores, show, cfg)
            tool._save_narrow()
            report["saved"] = True
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            read_all = _all_rows(_runtime_plain(tool, readback, record_passage_guid, cfg, template))
            check_scope(tool, before_all, read_all, plan, "after")
            rows_ok = readback_rows(read_all, plan, "after")
            require(export_hash(_export_texts(readback), plan["target_attachment_guids"], plan_intensity_guids(plan),
                        plan.get("shadow_guids") or []) == texts_hash,
                    "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "after_target_rows_live": target_rows(read_all, plan),
                           "saved_census": tool._dirty_census()})
            tool._write_json(RECORD_PATH, record)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized,
                           "readback_rows": rows_ok})
            tool._write_json(report_path(mode, run, passage=passage), report)
            _log("%s_APPLY_OK|run=%s|rows=%d|bays=%d|show_saved=1|level_saved=1|readback=1|record=%s"
                 % (MARK, run, len(plan["targets"]), len(plan["target_bays"]), RECORD_PATH))
            return report

        # REVERT
        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT|" + RECORD_PATH)
        record = tool._read_json(RECORD_PATH)
        check_record(record, passage)
        plan = record["plan"]
        drifts = revert_drifts(before_all, record)
        report["revert_drifts"] = drifts
        require(not drifts, "REVERT_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:4000]))
        reverted_model = revert_plain(tool, before_all, record)
        texts_hash = export_hash(_export_texts(show), plan["target_attachment_guids"], plan_intensity_guids(plan),
                        plan.get("shadow_guids") or [])
        backup = tool._backup(backup_prefix(revert=True, passage=passage), run)
        try:
            _write_transforms(tool, show, plan, "before", check_side="after")
            after_all = _all_rows(_runtime_plain(tool, show, record_passage_guid, cfg, template))
            check_scope(tool, before_all, after_all, plan, "before")
            require(not scope_differences(tool, reverted_model, after_all, plan, "before"), "REVERT_MODEL_MISMATCH")
            require(export_hash(_export_texts(show), plan["target_attachment_guids"], plan_intensity_guids(plan),
                        plan.get("shadow_guids") or []) == texts_hash,
                    "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            _write_transforms(tool, show, plan, "after")
            raise
        materialized = _materialize(scores, show, cfg)
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _all_rows(_runtime_plain(tool, readback, record_passage_guid, cfg, template))
        check_scope(tool, before_all, read_all, plan, "before")
        rows_ok = readback_rows(read_all, plan, "before")
        archived = RECORD_PATH + ".reverted-" + run
        record["status"] = "reverted"
        tool._write_json(RECORD_PATH, record)
        os.rename(RECORD_PATH, archived)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized,
                       "readback_rows": rows_ok})
        tool._write_json(report_path(mode, run, passage=passage), report)
        _log("%s_REVERT_OK|run=%s|rows=%d|show_saved=1|level_saved=1|readback=1|archived=%s"
             % (MARK, run, len(plan["targets"]), archived))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(mode, run, passage=passage), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s"
                         % (MARK, run, mode, int(report["saved"]), report["error"][:1500],
                            "" if report["saved"] else "|NOTHING SAVED"))
        raise


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    raw = globals().get("P01RIGPATTERN_ARGS")   # the runner global keeps its 6 Oct name for every passage
    try:
        args = check_args(raw)
    except Exception as error:  # noqa: BLE001 - args refusals get the same stop marker
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (mark_for_raw(raw), type(error).__name__, error))
        raise
    return _run(args)


if unreal is not None:
    main()
