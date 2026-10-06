"""Passage-agnostic lighting SCORES tool: DRY / APPLY / REVERT, one passage per run.

A passage's score (lighting_scores.json) is a per-bay sequence of looks over
the one P04 kit. Looks are presets: the base looks are read from the P04
prototype's ``lighting_looks.json``; passage variants and per-bay overrides
are applied on top. Every bay is a WingPair ORDINAL inside the passage's
PassageSettings range and is resolved to its CueGuid at run time, twice: by the
Show's own ``GetWingPairCueGuidsInPassage`` (declaration-proven,
InfinityStageShowAsset.h:131-133, .cpp:496-521) and by an independent
first..last walk; the two must agree. No code path finds a cue by label (P05
reuses labels); labels are compared only after the GUID resolve, as a drift
guard.

Proven pieces are IMPORTED from ``lighting_looks_apply.py`` (the P04 tool),
not copied: kit expansion, attachment construction, scratch-pair GUID minting
vessels, exhaustive attachment state, outside-target hash, backups, narrow
save, dirty census, test queueing. That file ends in ``if unreal is not None:
main()``, so importing it inside Unreal would RUN the P04 tool. The loader
below parses it, refuses unless the only top-level side effect is that final
guard, strips the guard, and executes the rest into a fresh module (never via
``import``, so the editor's Python module cache cannot serve a stale copy).
Every symbol used is checked by name and parameter list before use.

Modes: set globals through ``runpy.run_path(..., init_globals={...})``:
  LIGHTING_SCORES_MODE     DRY (default) | APPLY | REVERT
  LIGHTING_SCORES_PASSAGE  P01..P06 (required; no default)
  LIGHTING_SCORES_ACK_RECORDS   optional list of foreign active record paths the
                                operator has read and accepts as overlapping
  LIGHTING_SCORES_PROTOTYPE_ABSENT  optional 'AUTHOR_FALLBACK' (P04 only)

APPLY / REVERT: context gate (project, world, PIE off, Sequencer closed, clean
census, no ZZ_ actors), Show+level backup under Backups/PreLightingScoresP0N-*,
exclusive revert record written before mutation, in-memory rollback on any
failure, outside-target hash guard, per-passage shadow budget (after <= before:
swap, don't add), materialize ONLY this passage, save ONLY Show + level, read
the Show back and compare every field, queue SavedMasterMatchesShow. The
operator must then run BOTH run_saved_master_test_request.json and
run_scene_cut_test_request.json and read the results; "queued" is not a pass.
"""
from __future__ import annotations

import ast
import copy
import datetime
import glob
import hashlib
import inspect
import json
import math
import os
import re
import sys
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
SCORES_PATH = os.path.join(HERE, "lighting_scores.json")
P04_TOOL_PATH = os.path.join(HERE, "lighting_looks_apply.py")
VALID_MODES = ("DRY", "APPLY", "REVERT")
PASSAGE_KEY = re.compile(r"^P0[1-6]$")
VALID_ROLES = ("TOP", "LOW_SIDE", "BEAM", "PRACTICAL", "FILL", "UPLIGHT", "MOVER")
# 6 Oct round 2: PRACTICAL 2 -> 4 (P04 floor + hanging bulbs, P06 embers); FILL = soft fence-facing
# spots (P05 sky-curtain fills); UPLIGHT = small floor spots up a wing (P05 mountain pieces, P04 wing texture);
# MOVER = P05 club movers (C++ pending: data only, skipped with a warning, see requires_cpp).
ROLE_MAX = {"TOP": 2, "LOW_SIDE": 2, "BEAM": 1, "PRACTICAL": 4, "FILL": 2, "UPLIGHT": 2, "MOVER": 2}
AFTER_PASS = ("HOLD", "DECAY", "EXTINGUISH")
SHADOW_POLICIES = ("ALL", "ALTERNATE_LIT", "NONE")
UNITS = ("CANDELAS", "LUMENS")
FLICKER_ROOT = "/Game/InfinityStage/Lighting/MI_LF_Flicker_"
TESTS_REQUIRED = ("run_saved_master_test_request.json", "run_scene_cut_test_request.json")
VARIANT_FIELDS = {
    "intensity", "color_rgb_linear", "temperature_kelvin", "volumetric_scattering",
    "inner_cone_deg", "outer_cone_deg", "attenuation_cm", "location_cm",
    "rotation_rpy_deg", "flicker", "aim_wing_side", "aim_offset_pair_cm", "cast_shadows",
    # 5 Oct (P02 relight): a revived practical needs a lit body, not the dead-bulb sphere.
    # Replaced whole; validate_instrument re-checks mesh/style/emissive/transform.
    "visible_mesh",
    # 5 Oct (P04 ceiling strike): a fixed look-at POINT in pair space, for a spot aimed at
    # something that is not a side wing panel (the P04 ceiling border). The rotation is
    # computed offline from it (bay_fixtures) and _apply_live_aims leaves it alone.
    "aim_target_pair_cm",
    # 6 Oct round 2 (Gary note 59):
    #  keying       per-lamp strike-on-approach keys (DRAMA_KEYS), merged over the bay's distance keying, so ONE
    #               lamp can strike N bays ahead (P01 bay-20 beams seen in the distance) while the rest of the
    #               bay keeps the default 650 cm.
    #  drama        per-lamp FInfinityStageLightDrama slow-move keys (SLOW_MOVE_KEYS), written by the P04
    #               tool's _make_light (DRAMA_OVERRIDE_FIELDS, lighting_looks_apply.py:421-426).
    #  dim_tint     ORANGE | WHITE | PINK: the colour a dead bulb glows at when the dim_bulbs policy revives it.
    #  body_mode    STABLE | SLIGHT | FAIL: the bulb-glass behaviour the C++ agent is adding (no-op until then).
    #  requires_cpp a lamp that needs C++ not yet built (P05 movers): validated, then SKIPPED with a warning.
    "keying", "drama", "dim_tint", "body_mode", "requires_cpp",
}
# NO-CROSS-SHOT rule (Gary 5 Oct, P02: "those lights should not shoot through from
# L to R"). Enabled per passage by passages.<P>.no_cross_shots (true or a dict).
NO_CROSS_DEFAULTS = {"centre_tolerance_cm": 100.0, "nominal_panel_abs_y_cm": 900.0}
# The per-bay set is the P04 tool's own override set (lighting_looks_apply.py
# validate_config "allowed") plus flicker, which expand_bay's row.update carries.
BAY_OVERRIDE_FIELDS = {
    "intensity", "color_rgb_linear", "temperature_kelvin", "volumetric_scattering",
    "inner_cone_deg", "outer_cone_deg", "attenuation_cm", "location_cm",
    "aim_wing_side", "aim_offset_pair_cm", "flicker",
    "keying", "drama", "dim_tint", "body_mode",  # 6 Oct round 2, see VARIANT_FIELDS
}
SLOW_MOVE_KEYS = {"slow_move", "pan_amplitude_degrees", "tilt_amplitude_degrees", "period_seconds",
                  "phase_from_identity", "phase_cycles"}
BODY_BEHAVIOURS = ("STABLE", "SLIGHT", "FAIL")
DIM_TINTS = ("ORANGE", "WHITE", "PINK")
DRAMA_KEYS = {
    "strike_distance_cm", "ramp_distance_cm", "unstruck_intensity_scale", "after_pass",
    "ignition_stutter", "after_pass_distance_cm", "decay_distance_cm",
}

# name -> exact parameter names. A mismatch means the P04 tool changed under us.
REQUIRED_P04_FUNCTIONS = {
    "require": ("condition", "message"),
    "_read_json": ("path",),
    "_write_json": ("path", "value", "exclusive"),
    "_canonical": ("value",),
    "_sha256_file": ("path",),
    "_state_hash": ("value",),
    "expand_bay": ("config", "bay_row"),
    "_plain_is_light": ("attachment",),
    "_plain_casts": ("attachment",),
    "_guid_text": ("value",),
    "_enum_member": ("enum_type", "name"),
    "_dirty_census": (),
    "_require_context": ("allow_dirty_show",),
    "_is_light": ("attachment",),
    "_attachment_rows": ("attachments",),
    "_require_attachment_rows_equal": ("actual", "expected", "message"),
    "_rows_hash": ("rows",),
    "_pair_attachments": ("cue",),
    "_set_pair_attachments": ("show", "cue_index", "attachments"),
    "_plain_cues": ("show",),
    "_all_pair_rows": ("show",),
    "_look_at_rpy": ("source", "target", "label"),
    "_make_blank_light": (),
    "_make_light": ("row", "materials"),
    "_make_prop": ("row", "practical_meshes"),
    "_overwrite_vessel": ("vessel", "template"),
    "_materials": ("config",),
    "_practical_meshes": ("config",),
    "_backup": ("prefix", "run"),
    "_save_narrow": (),
    "_queue_master_test": ("world", "marker", "run"),
    "_outside_hash": ("all_rows", "target_guids"),
}
REQUIRED_P04_CONSTANTS = ("SHOW_PATH", "EXPECTED_WORLD", "LightingLooksError")
# Top-level calls the P04 module may make while loading (all side-effect free).
SAFE_TOP_LEVEL_CALLS = {
    "_load_attachment_state", "os.path.join", "os.path.dirname", "os.path.abspath",
    "os.path.normcase", "os.path.normpath", "re.compile", "tuple", "frozenset",
    "set", "dict", "list",
}


class LightingScoresError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise LightingScoresError(str(message))


def _finite(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise LightingScoresError("%s_NOT_A_NUMBER|value=%r" % (label, value))
    require(math.isfinite(number), "%s_NOT_FINITE|value=%r" % (label, value))
    return number


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path):
    with open(path, "rb") as handle:
        return _sha256_bytes(handle.read())


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


# --------------------------------------------------------------------------
# P04 tool loader (no import, no main()).
# --------------------------------------------------------------------------
def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else inner + "." + node.attr
    return None


def _is_main_guard(node):
    if not isinstance(node, ast.If) or node.orelse or len(node.body) != 1:
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
            and test.left.id == "unreal" and len(test.ops) == 1
            and isinstance(test.ops[0], ast.IsNot) and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None):
        return False
    stmt = node.body[0]
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "main"
            and not stmt.value.args and not stmt.value.keywords)


def _calls_are_safe(node):
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if _dotted(child.func) not in SAFE_TOP_LEVEL_CALLS:
                return False
    return True


def _top_level_ok(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Expr):
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value is None or _calls_are_safe(node.value)
    if isinstance(node, ast.Try):
        inner = list(node.body) + [stmt for handler in node.handlers for stmt in handler.body]
        inner += list(node.orelse) + list(node.finalbody)
        return all(isinstance(stmt, (ast.Import, ast.ImportFrom))
                   or (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant))
                   for stmt in inner)
    return False


def load_p04_tool(path=P04_TOOL_PATH, module_name="_lighting_looks_apply_for_scores"):
    """Execute the P04 tool's definitions without its trailing main() guard."""
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    guards = [index for index, node in enumerate(tree.body) if _is_main_guard(node)]
    require(len(guards) == 1 and guards[0] == len(tree.body) - 1,
            "P04_TOOL_MAIN_GUARD_SHAPE|guards=%s|statements=%d" % (guards, len(tree.body)))
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_ok(node, index),
                "P04_TOOL_TOP_LEVEL_SIDE_EFFECT|line=%d|node=%s"
                % (getattr(node, "lineno", -1), type(node).__name__))
    tree.body = tree.body[:-1]
    code = compile(tree, path, "exec")
    # The P04 module imports the shared comparer by name; drop any cached copy so
    # an edited comparer is never served stale (editor module cache, 2 Oct).
    sys.modules.pop("_infinity_attachment_state", None)
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(code, module.__dict__)  # noqa: S102 - our own reviewed project file.
    missing = []
    for name, params in sorted(REQUIRED_P04_FUNCTIONS.items()):
        function = getattr(module, name, None)
        if not callable(function):
            missing.append(name + ":absent")
            continue
        actual = tuple(inspect.signature(function).parameters)
        if actual != params:
            missing.append("%s:params=%s" % (name, ",".join(actual)))
    for name in REQUIRED_P04_CONSTANTS:
        if not hasattr(module, name):
            missing.append(name + ":absent")
    require(not missing, "P04_TOOL_API_DRIFT|" + ";".join(missing))
    module.SCORES_SOURCE_SHA256 = _sha256_bytes(raw)
    module.SCORES_SOURCE_PATH = path
    return module


# --------------------------------------------------------------------------
# Scores: load, derive looks, validate, expand.
# --------------------------------------------------------------------------
def load_scores(path=SCORES_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_base_looks(scores, scores_dir=HERE):
    path = os.path.join(scores_dir, scores["base_looks_source"])
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    pin = scores.get("base_looks_sha256_pin")
    digest = _sha256_path(path)
    require(pin is None or pin == digest,
            "BASE_LOOKS_PIN_MISMATCH|pinned=%s|actual=%s" % (pin, digest))
    looks = data.get("looks", {})
    used = {}
    for name in scores["base_looks_used"]:
        require(name in looks, "BASE_LOOK_MISSING|look=" + name)
        used[name] = copy.deepcopy(looks[name])
    return used, {"path": path, "sha256": digest}


def _apply_instrument_overrides(instrument, overrides, allowed, where):
    require(isinstance(overrides, dict) and set(overrides).issubset(allowed),
            "BAD_OVERRIDE_FIELDS|%s|fields=%s" % (where, ",".join(sorted(overrides))))
    row = copy.deepcopy(instrument)
    for key, value in overrides.items():
        if key == "location_cm":
            row["transform"]["location_cm"] = [float(v) for v in value]
        elif key == "rotation_rpy_deg":
            row["transform"]["rotation_rpy_deg"] = [float(v) for v in value]
        else:
            row[key] = copy.deepcopy(value)
    return row


def derive_variant(name, variant, base_looks):
    require(variant.get("base") in base_looks,
            "VARIANT_BASE_UNKNOWN|variant=%s|base=%s" % (name, variant.get("base")))
    base = base_looks[variant["base"]]
    overrides = variant.get("instrument_overrides", {})
    slots = [row["slot"] for row in base["instruments"]]
    unknown = sorted(set(overrides) - set(slots))
    require(not unknown, "VARIANT_SLOT_UNKNOWN|variant=%s|slots=%s" % (name, ",".join(unknown)))
    drops = set(variant.get("drop_slots", []))
    require(drops.issubset(slots), "VARIANT_DROP_UNKNOWN|variant=" + name)
    instruments = []
    for row in base["instruments"]:
        if row["slot"] in drops:
            continue
        instruments.append(_apply_instrument_overrides(
            row, overrides.get(row["slot"], {}), VARIANT_FIELDS,
            "variant=%s|slot=%s" % (name, row["slot"])))
    # 6 Oct round 2: a variant may ADD whole instruments (P04 hanging bulbs, P05 fills/movers, P06 embers).
    # Each is a full row, validated like a base row; its slot may not shadow a base slot.
    for row in variant.get("add_instruments", []):
        require(isinstance(row, dict) and row.get("slot") and row["slot"] not in slots
                and set(row) - {"slot", "role", "type", "transform", "intensity_units", "rect_source_width_cm",
                                "rect_source_height_cm"} <= VARIANT_FIELDS | {"note"},
                "VARIANT_ADD_BAD|variant=%s|slot=%s" % (name, row.get("slot") if isinstance(row, dict) else row))
        instruments.append(copy.deepcopy(row))
    return {"intent": variant.get("intent", ""), "base": variant["base"], "instruments": instruments}


def resolve_looks(scores, base_looks):
    looks = {}
    for name, look in base_looks.items():
        looks[name] = copy.deepcopy(look)
    for name, look in scores.get("local_looks", {}).items():
        require(name not in looks, "LOOK_NAME_CLASH|look=" + name)
        looks[name] = copy.deepcopy(look)
    for name, variant in scores.get("variants", {}).items():
        require(name not in looks, "LOOK_NAME_CLASH|look=" + name)
        looks[name] = derive_variant(name, variant, base_looks)
    for name, look in looks.items():
        validate_look(name, look)
    return looks


def validate_look(name, look):
    instruments = look.get("instruments", [])
    require(instruments, "LOOK_EMPTY|look=" + name)
    slots = [row.get("slot") for row in instruments]
    require(len(slots) == len(set(slots)), "DUPLICATE_SLOT|look=" + name)
    counts = {role: 0 for role in VALID_ROLES}
    for row in instruments:
        validate_instrument(row, "look=%s|slot=%s" % (name, row.get("slot")))
        counts[row["role"]] += 1
    for role, maximum in ROLE_MAX.items():
        require(counts[role] <= maximum, "ROLE_COUNT|look=%s|role=%s|count=%d" % (name, role, counts[role]))
    require(counts["PRACTICAL"] >= 1, "PRACTICALS_EVERYWHERE|look=" + name)


def validate_instrument(row, where):
    """Single-row checks shared by looks and expanded fixtures."""
    role = row.get("role")
    require(role in VALID_ROLES, "BAD_ROLE|%s|role=%s" % (where, role))
    require(row.get("type") in ("SPOT", "POINT", "RECT"), "BAD_LIGHT_TYPE|" + where)
    require(row.get("intensity_units") in UNITS, "BAD_UNITS|" + where)
    require(_finite(row.get("intensity"), "INTENSITY") >= 0.0, "NEGATIVE_INTENSITY|" + where)
    require(_finite(row.get("attenuation_cm"), "ATTENUATION") > 0.0, "BAD_ATTENUATION|" + where)
    rgb = row.get("color_rgb_linear", [])
    require(len(rgb) == 3 and all(_finite(v, "RGB") >= 0.0 for v in rgb), "BAD_RGB|" + where)
    require(1000.0 <= _finite(row.get("temperature_kelvin"), "TEMPERATURE") <= 15000.0,
            "BAD_TEMPERATURE|" + where)
    require(_finite(row.get("volumetric_scattering"), "VOLUMETRIC") >= 0.0, "BAD_VOLUMETRIC|" + where)
    transform = row.get("transform", {})
    require(len(transform.get("location_cm", [])) == 3
            and len(transform.get("rotation_rpy_deg", [])) == 3, "BAD_TRANSFORM|" + where)
    if row["type"] == "SPOT":
        inner = _finite(row.get("inner_cone_deg"), "INNER_CONE")
        outer = _finite(row.get("outer_cone_deg"), "OUTER_CONE")
        require(0.0 <= inner <= outer <= 89.0, "BAD_CONE|" + where)
    if row["type"] == "RECT":
        _finite(row.get("rect_source_width_cm"), "RECT_W")
        _finite(row.get("rect_source_height_cm"), "RECT_H")
    require(isinstance(row.get("cast_shadows"), bool), "CAST_SHADOWS_UNDECLARED|" + where)
    # 5 Oct ~16:25 Gary: "all lights should be allowed to cast shadows". The LOW_SIDE-only rule
    # (NON_SIDE_SHADOW_CASTER) is gone; the per-passage shadow BUDGET (build_score_plan) still governs.
    flicker = row.get("flicker", {})
    require("mode" in flicker and "material" in flicker, "FLICKER_UNDECLARED|" + where)
    require(flicker["material"] is None or str(flicker["material"]).startswith(FLICKER_ROOT),
            "FLICKER_MATERIAL_UNKNOWN|" + where)
    if role == "TOP":
        require(row["slot"].rsplit("_", 1)[-1] in ("L", "R"), "TOP_SLOT_SIDE_UNKNOWN|" + where)
    if "aim_target_pair_cm" in row:
        point = row.get("aim_target_pair_cm")
        require(row["type"] == "SPOT" and "aim_wing_side" not in row and "aim_offset_pair_cm" not in row
                and isinstance(point, list) and len(point) == 3 and all(math.isfinite(float(v)) for v in point),
                "AIM_TARGET_BAD|" + where)
    if "aim_wing_side" in row or "aim_offset_pair_cm" in row:
        require(row["type"] == "SPOT" and row.get("aim_wing_side") in ("LEFT", "RIGHT"),
                "WING_AIM_BAD|" + where)
        offset = row.get("aim_offset_pair_cm")
        require(isinstance(offset, list) and len(offset) == 3
                and all(math.isfinite(float(v)) for v in offset), "WING_AIM_OFFSET_BAD|" + where)
    keying = row.get("keying")
    if keying is not None:
        require(isinstance(keying, dict) and keying, "LAMP_KEYING_BAD|" + where)
        _check_drama(keying, "lamp|" + where)
    drama = row.get("drama")
    if drama is not None:
        require(isinstance(drama, dict) and set(drama) <= SLOW_MOVE_KEYS and row["type"] == "SPOT",
                "LAMP_DRAMA_BAD|" + where)
        if "slow_move" in drama:
            require(isinstance(drama["slow_move"], bool), "LAMP_DRAMA_BAD|" + where)
        if "phase_from_identity" in drama:
            require(isinstance(drama["phase_from_identity"], bool), "LAMP_DRAMA_BAD|" + where)
        for key in ("pan_amplitude_degrees", "tilt_amplitude_degrees"):
            if key in drama:
                require(0.0 <= _finite(drama[key], key) <= 45.0, "LAMP_DRAMA_RANGE|%s|%s" % (key, where))
        if "period_seconds" in drama:
            require(_finite(drama["period_seconds"], "PERIOD") >= 1.0, "LAMP_DRAMA_RANGE|period|" + where)
        if "phase_cycles" in drama:
            require(0.0 <= _finite(drama["phase_cycles"], "PHASE") <= 1.0, "LAMP_DRAMA_RANGE|phase|" + where)
    require(row.get("dim_tint") in (None,) + DIM_TINTS, "DIM_TINT_BAD|" + where)
    require(row.get("body_mode") in (None,) + BODY_BEHAVIOURS and (row.get("body_mode") is None or role == "PRACTICAL"),
            "BODY_MODE_BAD|" + where)
    if row.get("requires_cpp") is not None:
        require(isinstance(row["requires_cpp"], str) and row["requires_cpp"].strip() and role == "MOVER",
                "REQUIRES_CPP_BAD|" + where)
    if role == "MOVER":
        require(row.get("requires_cpp"), "MOVER_WITHOUT_CPP_GATE|" + where)
    if role == "PRACTICAL":
        visible = row.get("visible_mesh", {})
        require(str(visible.get("mesh", "")).startswith(("/Game/", "/Engine/")),
                "PRACTICAL_MESH_MISSING|" + where)
        require(bool(visible.get("style")) and isinstance(visible.get("emissive"), bool),
                "PRACTICAL_BODY_UNDECLARED|" + where)
        require(len(visible.get("rotation_rpy_deg", [])) == 3
                and len(visible.get("scale", [])) == 3
                and all(_finite(v, "BODY_SCALE") > 0.0 for v in visible["scale"]),
                "PRACTICAL_BODY_TRANSFORM_BAD|" + where)
        validate_body_material(row, where)


def _fraction(position, count):
    return 0.0 if count <= 1 else float(position) / float(count - 1)


def _check_drama(drama, where):
    require(set(drama).issubset(DRAMA_KEYS), "BAD_DRAMA_FIELDS|%s|fields=%s" % (where, ",".join(sorted(drama))))
    if "after_pass" in drama:
        require(drama["after_pass"] in AFTER_PASS, "BAD_AFTER_PASS|" + where)
    if "ignition_stutter" in drama:
        require(0.0 <= _finite(drama["ignition_stutter"], "STUTTER") <= 1.0, "BAD_STUTTER|" + where)
    if "unstruck_intensity_scale" in drama:
        require(0.0 <= _finite(drama["unstruck_intensity_scale"], "UNSTRUCK") <= 1.0, "BAD_UNSTRUCK|" + where)
    if "strike_distance_cm" in drama:
        require(0.0 <= _finite(drama["strike_distance_cm"], "STRIKE") <= 6000.0, "BAD_STRIKE|" + where)
    for key in ("ramp_distance_cm", "decay_distance_cm"):
        if key in drama:
            require(_finite(drama[key], key.upper()) >= 1.0, "BAD_%s|%s" % (key.upper(), where))
    if "after_pass_distance_cm" in drama:
        require(_finite(drama["after_pass_distance_cm"], "AFTER_PASS_DISTANCE") >= 0.0,
                "BAD_AFTER_PASS_DISTANCE|" + where)


def expand_score(passage_key, passage):
    """Return one bay spec per ordinal 1..expected_bay_count (exact cover)."""
    count = int(passage["expected_bay_count"])
    require(count >= 1, "BAD_BAY_COUNT|passage=" + passage_key)
    specs = {}
    for seg_index, segment in enumerate(passage["segments"]):
        first, last = [int(v) for v in segment["bays"]]
        require(1 <= first <= last <= count,
                "SEGMENT_RANGE|passage=%s|segment=%d" % (passage_key, seg_index))
        span = last - first + 1
        generator = segment.get("generator")
        for position in range(span):
            ordinal = first + position
            require(ordinal not in specs,
                    "BAY_COVERED_TWICE|passage=%s|bay=%d" % (passage_key, ordinal))
            if generator == "FAILING":
                spec = _failing_spec(segment, position, span)
            else:
                require(generator is None, "UNKNOWN_GENERATOR|" + str(generator))
                cycle = segment["cycle"]
                require(cycle, "EMPTY_CYCLE|passage=%s|segment=%d" % (passage_key, seg_index))
                source = cycle[position % len(cycle)]
                spec = {
                    "look": source["look"],
                    "level": float(source.get("level", 1.0)),
                    "mirror": list(source.get("mirror", [])),
                    "overrides": copy.deepcopy(source.get("overrides", {})),
                    "drama": copy.deepcopy(source.get("drama", {})),
                    "drop_slots": [],
                    "if_absent": copy.deepcopy(source.get("if_absent")),
                    "note": source.get("note", ""),
                }
                cascade = segment.get("strike_cascade")
                if cascade:
                    spec["drama"].update({
                        "strike_distance_cm": float(cascade["base_strike_cm"])
                        + position * float(cascade["extra_per_bay_cm"]),
                        "ramp_distance_cm": float(cascade["ramp_distance_cm"]),
                        "ignition_stutter": float(cascade["ignition_stutter"]),
                    })
            spec["ordinal"] = ordinal
            spec["segment"] = seg_index
            specs[ordinal] = spec
    missing = [ordinal for ordinal in range(1, count + 1) if ordinal not in specs]
    require(not missing, "BAYS_UNCOVERED|passage=%s|bays=%s" % (passage_key, missing))
    return [specs[ordinal] for ordinal in range(1, count + 1)]


def _failing_spec(segment, position, span):
    fraction = _fraction(position, span)
    level_from = _finite(segment["level_from"], "LEVEL_FROM")
    level_to = _finite(segment["level_to"], "LEVEL_TO")
    require(level_from >= level_to > 0.0, "FAILING_LEVEL_NOT_DECAYING")
    stutter_from = _finite(segment["stutter_from"], "STUTTER_FROM")
    stutter_to = _finite(segment["stutter_to"], "STUTTER_TO")
    require(0.0 <= stutter_from <= stutter_to <= 1.0, "FAILING_STUTTER_NOT_RISING")
    level = level_from + (level_to - level_from) * fraction
    drops = []
    for step in segment.get("slot_failures", []):
        if fraction + 1.0e-12 >= float(step["at_fraction"]):
            drops.extend(step["slots"])
    drama = {"ignition_stutter": stutter_from + (stutter_to - stutter_from) * fraction}
    for step in segment.get("after_pass_steps", []):
        if fraction + 1.0e-12 >= float(step["at_fraction"]):
            drama["after_pass"] = step["after_pass"]
            for key in ("after_pass_distance_cm", "decay_distance_cm"):
                if key in step:
                    drama[key] = float(step[key])
    overrides = {}
    for step in segment.get("colour_steps", []):
        if fraction + 1.0e-12 >= float(step["at_fraction"]):
            for slot, values in step["overrides"].items():
                overrides.setdefault(slot, {}).update(copy.deepcopy(values))
    return {
        "look": segment["look"],
        "level": level,
        "mirror": list(segment.get("mirror_alternate", [])) if position % 2 else [],
        "overrides": overrides,
        "drama": drama,
        "drop_slots": sorted(set(drops)),
        "if_absent": None,
        "note": "failing %.2f" % fraction,
    }


def bay_fixtures(tool, scores, looks, passage_key, spec):
    """Expand one bay with the P04 tool's own expand_bay over a derived look."""
    look_name = spec["look"]
    look = copy.deepcopy(looks[look_name])
    slots = {row["slot"] for row in look["instruments"]}
    where = "passage=%s|bay=%d" % (passage_key, spec["ordinal"])
    require(set(spec["drop_slots"]).issubset(slots), "DROP_SLOT_UNKNOWN|" + where)
    require(set(spec["overrides"]).issubset(slots), "BAY_OVERRIDE_SLOT_UNKNOWN|" + where)
    for slot, values in spec["overrides"].items():
        require(isinstance(values, dict) and set(values).issubset(BAY_OVERRIDE_FIELDS),
                "BAD_BAY_OVERRIDE_FIELDS|%s|slot=%s" % (where, slot))
    require(set(spec["mirror"]).issubset({"LOW_SIDE", "BEAM", "PRACTICAL"}),
            "BAD_MIRROR_ROLES|" + where)
    require(_finite(spec["level"], "LEVEL") > 0.0, "BAD_LEVEL|" + where)
    look["instruments"] = [row for row in look["instruments"] if row["slot"] not in spec["drop_slots"]]
    require(look["instruments"], "BAY_HAS_NO_INSTRUMENTS|" + where)
    keying = copy.deepcopy(scores["distance_keying_default"])
    _check_drama(spec["drama"], where)
    keying.update(copy.deepcopy(spec["drama"]))
    config = {
        "fixture_label_prefix": scores["fixture_label_prefix_format"] % int(passage_key[1:]),
        "looks": {look_name: look},
        "distance_keying": keying,
    }
    bay_row = {
        "bay_index": spec["ordinal"],
        "look": look_name,
        "level_scale": spec["level"],
        "mirror_roles": list(spec["mirror"]),
        "instrument_overrides": copy.deepcopy(spec["overrides"]),
    }
    fixtures = tool.expand_bay(config, bay_row)
    spec["cpp_pending"] = _drop_cpp_pending(fixtures, where)
    _apply_lamp_keying(fixtures)
    _apply_dim_bulbs(scores, passage_key, spec["ordinal"], fixtures)
    _mirror_explicit_aims(fixtures, spec)
    _apply_fixed_aim_points(tool, fixtures, spec)
    _resolve_lamp_bodies(fixtures, where)
    _add_bulb_caps(scores, fixtures)
    _assign_body_behaviours(scores, passage_key, spec["ordinal"], fixtures)
    for row in fixtures:
        if row["authored_kind"] == "LIGHT":
            validate_instrument(row, "%s|look=%s|slot=%s" % (where, look_name, row["slot"]))
    return fixtures


# --------------------------------------------------------------------------
# 6 Oct round 2 (Gary note 59) fixture passes. Each is a no-op unless its data is present
# (per-lamp keying / requires_cpp rows, scores["dim_bulbs"], scores["bulb_caps"],
# scores["bulb_body_behaviours"]), so a score without them expands exactly as before.
# --------------------------------------------------------------------------
def _drop_cpp_pending(fixtures, where):
    """Lamps that need C++ not yet built (P05 movers): validated as data, then removed from the
    bay with a warning row, so APPLY never authors a half-working lamp."""
    pending = []
    for row in list(fixtures):
        if row.get("authored_kind") == "LIGHT" and row.get("requires_cpp"):
            validate_instrument(row, where + "|slot=" + row["slot"])
            pending.append({"slot": row["slot"], "label": row["label"], "role": row["role"],
                            "requires_cpp": row["requires_cpp"],
                            "warning": "SKIPPED_PENDING_CPP|%s|slot=%s|needs=%s" % (where, row["slot"], row["requires_cpp"])})
            fixtures.remove(row)
    return pending


def _apply_lamp_keying(fixtures):
    """Per-lamp strike keys over the bay's distance keying (VARIANT_FIELDS 'keying')."""
    for row in fixtures:
        if row.get("authored_kind") == "LIGHT" and row.get("keying"):
            row["distance_keying"].update(copy.deepcopy(row["keying"]))


def _stable_unit(*parts):
    """Deterministic [0,1) from text (sha1): no random stream, so no draw-order re-rolls across runs."""
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16) / float(16 ** 8)


def _apply_dim_bulbs(scores, passage_key, ordinal, fixtures):
    """Every PRACTICAL lamp left at 0 becomes a DIM bulb: a tiny real point light in orange, white or pink and,
    on a Sphere bulb body, a low-glowing glass body (mode DIM). Gary 6 Oct ~00:30."""
    policy = scores.get("dim_bulbs")
    if not policy or not policy.get("enabled"):
        return
    tints = policy["tints"]
    choices = policy["passage_tints"][passage_key]
    bodies = {row["paired_slot"]: row for row in fixtures if row.get("role") == "PRACTICAL_BODY"}
    for row in fixtures:
        if row.get("authored_kind") != "LIGHT" or row["role"] != "PRACTICAL" or float(row["intensity"]) > 0.0:
            continue
        tint = row.get("dim_tint") or choices[int(_stable_unit(passage_key, ordinal, row["slot"]) * len(choices))]
        require(tint in tints and row["intensity_units"] == "LUMENS",
                "DIM_BULB_BAD|%s|B%02d|%s" % (passage_key, ordinal, row["slot"]))
        row.update({"intensity": float(policy["lumens"]), "attenuation_cm": float(policy["attenuation_cm"]),
                    "volumetric_scattering": float(policy["volumetric_scattering"]),
                    "color_rgb_linear": list(tints[tint]["rgb"]), "temperature_kelvin": float(tints[tint]["kelvin"]),
                    "flicker": {"mode": "STEADY", "material": None}, "dim_bulb": tint})
        visible = row["visible_mesh"]
        if visible["mesh"] == BULB_MESH:
            visible["emissive"] = True
            visible["material"] = {"parent": policy["body_parent"], "mode": "DIM"}
            if row["slot"] in bodies:
                bodies[row["slot"]]["emissive"] = True


def _add_bulb_caps(scores, fixtures):
    """A Sphere body alone reads as a ball; a small dull screw cap above it makes it a light bulb (no real bulb mesh
    exists in Content: searched 6 Oct). One extra PROP per Sphere-bodied practical, placed from the body's own
    transform, derived create-only like the bodies."""
    caps = scores.get("bulb_caps")
    if not caps or not caps.get("enabled"):
        return
    for prop in [row for row in fixtures if row.get("role") == "PRACTICAL_BODY"]:
        source = prop["body"]["source_mesh"] if prop.get("body") else prop["mesh"]
        if source != BULB_MESH:
            continue
        sx, sy, sz = [float(v) for v in prop["transform"]["scale"]]
        height = sz * 100.0 * float(caps["height_fraction"])
        location = list(prop["transform"]["location_cm"])
        location[2] += sz * 50.0 + height * 0.5 - float(caps["overlap_cm"])
        colour, intensity = list(CAP_COLOUR), CAP_INTENSITY
        mi, mesh = _body_names(CAP_MESH, caps["parent"], colour, intensity)
        require(prop["label"].endswith("_BODY"), "CAP_LABEL|" + prop["label"])
        fixtures.append({
            "slot": prop["paired_slot"] + "_CAP", "paired_slot": prop["paired_slot"], "role": "PRACTICAL_CAP",
            "authored_kind": "PROP", "label": prop["label"][:-len("_BODY")] + "_CAP",
            "bay_index": prop["bay_index"], "look": prop["look"], "mesh": mesh, "style": "bulb screw cap",
            "emissive": False,
            "transform": {"location_cm": location, "rotation_rpy_deg": [0.0, 0.0, 0.0],
                          "scale": [sx * float(caps["width_fraction"]), sy * float(caps["width_fraction"]),
                                    height / 100.0]},
            "cast_shadows": False,
            "body": {"source_mesh": CAP_MESH, "parent": caps["parent"], "mode": "CAP", "colour": colour,
                     "intensity": intensity, "mi": mi, "mesh": mesh, "flicker_follows_light": False},
        })


def _assign_body_behaviours(scores, passage_key, ordinal, fixtures):
    """Gary 6 Oct: 'a flickering and dying bulb, not all bulbs! some should flicker only slightly and others be
    stable'. Each practical body gets STABLE / SLIGHT / FAIL (an explicit body_mode on the lamp wins, else a
    stable hash split). DATA ONLY until the C++ per-attachment body option exists: carried on the plan, written
    by nothing (scores["bulb_body_behaviours"]["cpp_field"] names the field once the patch lands)."""
    policy = scores.get("bulb_body_behaviours")
    if not policy:
        return
    lights = {row["slot"]: row for row in fixtures if row.get("authored_kind") == "LIGHT"}
    fail, slight = float(policy["fractions"]["FAIL"]), float(policy["fractions"]["SLIGHT"])
    for prop in fixtures:
        if prop.get("role") != "PRACTICAL_BODY":
            continue
        explicit = lights[prop["paired_slot"]].get("body_mode")
        if explicit:
            mode = explicit
        else:
            u = _stable_unit("body", passage_key, ordinal, prop["paired_slot"])
            mode = "FAIL" if u < fail else ("SLIGHT" if u < fail + slight else "STABLE")
        prop["body_behaviour"] = {"mode": mode,
                                  "seed": int(_stable_unit("seed", passage_key, ordinal, prop["paired_slot"]) * 2 ** 31),
                                  "authored": False, "cpp_field": policy.get("cpp_field")}


def _mirror_explicit_aims(fixtures, spec):
    """Aim-aware mirroring (5 Oct). The P04 expand_bay mirrors a role by negating
    location y and yaw only; a LOOK-level aim_wing_side / aim_offset_pair_cm is left
    pointing at the original side, so a mirrored, wing-aimed lamp would shoot across
    the stage. Flip the side and negate the offset's y for mirrored rows, unless the
    BAY override set that field (bay overrides are absolute, like location_cm)."""
    mirrored = set(spec["mirror"])
    for row in fixtures:
        if row.get("authored_kind") != "LIGHT" or row["role"] not in mirrored or "aim_wing_side" not in row:
            continue
        bay_override = spec["overrides"].get(row["slot"], {})
        if "aim_wing_side" not in bay_override:
            row["aim_wing_side"] = {"LEFT": "RIGHT", "RIGHT": "LEFT"}.get(row["aim_wing_side"], row["aim_wing_side"])
        if "aim_offset_pair_cm" not in bay_override and isinstance(row.get("aim_offset_pair_cm"), list):
            offset = [float(v) for v in row["aim_offset_pair_cm"]]
            row["aim_offset_pair_cm"] = [offset[0], -offset[1], offset[2]]
        row["aim_mirrored"] = True


def _apply_fixed_aim_points(tool, fixtures, spec):
    """aim_target_pair_cm rows: mirror the point with the row (negate y, unless the
    bay override set it) and point the spot at it with the P04 tool's own look-at."""
    mirrored = set(spec["mirror"])
    for row in fixtures:
        if row.get("authored_kind") != "LIGHT" or row.get("aim_target_pair_cm") is None:
            continue
        point = [float(v) for v in row["aim_target_pair_cm"]]
        if row["role"] in mirrored and "aim_target_pair_cm" not in spec["overrides"].get(row["slot"], {}):
            point[1] = -point[1]
            row["aim_mirrored"] = True
        row["aim_target_pair_cm"] = point
        row["transform"]["rotation_rpy_deg"] = list(tool._look_at_rpy(
            row["transform"]["location_cm"], point, row.get("label", row["slot"])))


def no_cross_config(passage):
    """None when the passage does not enable the rule; else the merged settings."""
    raw = passage.get("no_cross_shots")
    if raw in (None, False):
        return None
    cfg = dict(NO_CROSS_DEFAULTS)
    if raw is not True:
        require(isinstance(raw, dict) and raw.get("enabled", True) is True
                and set(raw).issubset(set(NO_CROSS_DEFAULTS) | {"enabled", "note", "bays", "exempt_bays"}),
                "BAD_NO_CROSS_CONFIG|" + _canonical(raw))
        cfg.update({k: float(v) for k, v in raw.items() if k in NO_CROSS_DEFAULTS})
        if "bays" in raw:  # check only these ordinals (bays where the rule can pass)
            first, last = [int(v) for v in raw["bays"]]
            require(1 <= first <= last <= int(passage["expected_bay_count"]), "BAD_NO_CROSS_BAYS|" + _canonical(raw))
            cfg["bays"] = [first, last]
        if "exempt_bays" in raw:  # 6 Oct: named exceptions inside the range (each must be a reasoned look choice)
            exempt = sorted(int(v) for v in raw["exempt_bays"])
            require(all(1 <= v <= int(passage["expected_bay_count"]) for v in exempt), "BAD_NO_CROSS_EXEMPT|" + _canonical(raw))
            cfg["exempt_bays"] = exempt
    require(0.0 <= cfg["centre_tolerance_cm"] < cfg["nominal_panel_abs_y_cm"], "BAD_NO_CROSS_TOLERANCE")
    return cfg


def _spot_aim_target(row, cfg, live_goal=None):
    """Where a SPOT's beam goes, in pair space: (target_cm, basis).

    Wing-aimed rows (explicit aim_wing_side, or a TOP auto-aimed at its slot's
    side by _apply_live_aims) go to the panel + offset: the LIVE panel when given,
    else a nominal panel at +-nominal_panel_abs_y_cm (LEFT = -y, measured from the
    live P02 record: L panels y<0, R panels y>0). Fixed-rotation rows follow
    their rotation (UE X-forward, [roll, pitch, yaw]) to the floor or to their
    attenuation radius, whichever comes first."""
    source = [float(v) for v in row["transform"]["location_cm"]]
    if row.get("aim_target_pair_cm") is not None:
        return [float(v) for v in row["aim_target_pair_cm"]], "AIM_POINT"
    explicit = row.get("aim_wing_side")
    if explicit is not None or row["role"] == "TOP":
        if live_goal is not None:
            return [float(v) for v in live_goal], "LIVE_PANEL"
        if explicit is None:
            sign, offset = (-1.0 if row["slot"].rsplit("_", 1)[-1] == "L" else 1.0), [0.0, 0.0, 0.0]
            basis = "TOP_AUTO_AIM_NOMINAL"
        else:
            sign, offset = (-1.0 if explicit == "LEFT" else 1.0), [float(v) for v in row["aim_offset_pair_cm"]]
            basis = "WING_AIM_NOMINAL"
        return [offset[0], sign * cfg["nominal_panel_abs_y_cm"] + offset[1], offset[2]], basis
    pitch, yaw = [math.radians(float(v)) for v in row["transform"]["rotation_rpy_deg"][1:]]
    forward = [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)]
    reach = float(row["attenuation_cm"])
    if forward[2] < -1.0e-9 and source[2] > 0.0:
        reach = min(reach, source[2] / -forward[2])
    return [source[i] + reach * forward[i] for i in range(3)], "FIXED_ROTATION"


def no_cross_rows(passage_key, ordinal, fixtures, cfg, live_goals=None):
    """One row per SPOT: source y, target y, verdict. A beam may not travel past the
    stage centre line (y = 0) to the other side: the target y must share the source
    y's sign, or (TOP only) lie within centre_tolerance_cm of the centre. A source
    within the tolerance of the centre is a centre lamp and cannot cross. With
    live_goals, a wing-aimed non-TOP lamp must also stand on the stage side of the
    live panel it lights (|source y| < |panel y|), or it would shoot through it."""
    rows = []
    tol = cfg["centre_tolerance_cm"]
    if "bays" in cfg and not cfg["bays"][0] <= int(ordinal) <= cfg["bays"][1]:
        return rows
    if int(ordinal) in cfg.get("exempt_bays", []):
        return rows
    for row in fixtures:
        if row.get("authored_kind") != "LIGHT" or row.get("type") != "SPOT":
            continue
        goal = (live_goals or {}).get(row["label"])
        target, basis = _spot_aim_target(row, cfg, goal)
        source_y, target_y = float(row["transform"]["location_cm"][1]), float(target[1])
        if abs(source_y) <= tol:
            verdict = "OK_CENTRE_SOURCE"
        elif source_y * target_y > 0.0:
            verdict = "OK_SAME_SIDE"
        elif row["role"] == "TOP" and abs(target_y) <= tol:
            verdict = "OK_TOP_CENTRE_TOLERANCE"
        else:
            verdict = "CROSS"
        if basis == "AIM_POINT" and verdict.startswith("OK") and abs(source_y) > tol:
            # A fixed aim point is not a wing that stops the beam: follow the beam on to
            # its attenuation radius; its far end may not cross either.
            delta = [target[i] - float(row["transform"]["location_cm"][i]) for i in range(3)]
            length = math.sqrt(sum(v * v for v in delta))
            end_y = source_y + delta[1] / length * float(row["attenuation_cm"])
            if not (source_y * end_y > 0.0 or (row["role"] == "TOP" and abs(end_y) <= tol)):
                verdict = "CROSS_BEYOND_TARGET|end_y=%.0f" % end_y
        if (verdict == "OK_SAME_SIDE" and goal is not None and row["role"] != "TOP"
                and row.get("aim_wing_side") is not None and abs(source_y) >= abs(target_y)):
            verdict = "BEHIND_PANEL"
        rows.append({"bay": int(ordinal), "slot": row["slot"], "label": row.get("label", ""),
                     "role": row["role"], "source_y": round(source_y, 1), "target_y": round(target_y, 1),
                     "target_cm": [round(v, 1) for v in target], "basis": basis,
                     "mirrored_aim": bool(row.get("aim_mirrored", False)), "verdict": verdict})
    bad = [r for r in rows if not r["verdict"].startswith("OK")]
    require(not bad, "NO_CROSS_SHOT|passage=%s|bay=%d|%s" % (passage_key, int(ordinal), ";".join(
        "slot=%s,role=%s,source_y=%.0f,target_y=%.0f,basis=%s,verdict=%s"
        % (r["slot"], r["role"], r["source_y"], r["target_y"], r["basis"], r["verdict"]) for r in bad)))
    return rows


# --------------------------------------------------------------------------
# Lamp bodies with a material (5 Oct). FInfinityCueAttachment has NO material
# field (InfinityStageTypes.h:427-478) and a mesh-only prop is an
# AStaticMeshActor that only gets SetStaticMesh (InfinityStagePassageActor.cpp:
# 951-956), so a body's look comes from its MESH ASSET's own slot material. A
# visible_mesh.material spec therefore resolves to two derived, content-named
# assets under BODY_ASSET_DIR: an MI of an existing emissive parent, and a
# duplicate of the source mesh whose slot 0 is that MI. They are CREATE-ONLY:
# an existing asset is reused only if it already holds exactly the planned
# values, never edited; REVERT deletes only what its own record created and
# nothing that any attachment in the Show still references. Rows without
# visible_mesh.material are untouched (every pre-5-Oct look).
# --------------------------------------------------------------------------
BODY_ASSET_DIR = "/Game/InfinityStage/Lighting/Bulbs"
BODY_PARENTS = {
    # M_UP_TubeEmissive: unlit, emissive = Colour * Intensity * PerInstanceCustomData[3] (const default 1.0 off ISMs)
    # (underpass_tubes_apply.py:8, 58-79); on disk under Content/InfinityStage/RigAtmos/Underpass/Materials.
    "/Game/InfinityStage/RigAtmos/Underpass/Materials/M_UP_TubeEmissive": ("Colour", "Intensity"),
}
# 6 Oct round 2 (Gary note 59: "make all the dead bulbs minimally glowing ... a bulb can still glow orange, white,
# pink, and cast a small reflection"): the DEAD body mode is gone. A dead bulb is now a DIM lamp: a tiny real
# point light (DIM_MAX_LUMENS at most, short attenuation) plus a low-glowing glass body; CAP is the bulb's metal
# screw cap (a second, dull prop) that makes a Sphere read as a light bulb.
BODY_MODES = ("MATCH_LIGHT", "DIM", "CAP")
BODY_DIM_INTENSITY = 1.5
DIM_MAX_LUMENS = 40.0
DIM_MAX_ATTENUATION_CM = 200.0
CAP_MESH = "/Engine/BasicShapes/Cylinder"
CAP_COLOUR = [0.42, 0.32, 0.16]
CAP_INTENSITY = 0.25
BULB_MESH = "/Engine/BasicShapes/Sphere"


def kelvin_rgb_linear(kelvin):
    """Blackbody tint, linear RGB normalised to max 1 (Tanner Helland fit, sRGB-decoded). Inferred match to UE's
    use_temperature tint: both are blackbody, the exact UE curve is in private engine source we do not have."""
    t = max(1000.0, min(40000.0, float(kelvin))) / 100.0
    if t <= 66.0:
        r, g = 255.0, 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19.0 else 138.5177312231 * math.log(t - 10.0) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60.0) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60.0) ** -0.0755148492)
        b = 255.0
    srgb = [max(0.0, min(255.0, v)) / 255.0 for v in (r, g, b)]
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in srgb]
    peak = max(lin)
    return [v / peak for v in lin]


def body_emission(light_row, mode):
    """(colour, intensity) for a body: the light's colour x its Kelvin tint, brightness from its output
    (MATCH_LIGHT) or the fixed low glow (DIM); CAP is a fixed dull brass."""
    if mode == "CAP":
        return list(CAP_COLOUR), CAP_INTENSITY
    tint = kelvin_rgb_linear(light_row["temperature_kelvin"])
    raw = [float(c) * k for c, k in zip(light_row["color_rgb_linear"], tint)]
    peak = max(raw)
    require(peak > 0.0, "BODY_COLOUR_BLACK|slot=" + light_row["slot"])
    if mode == "DIM":
        return [round(v / peak, 3) for v in raw], BODY_DIM_INTENSITY
    lumens = float(light_row["intensity"]) * (1.0 if light_row["intensity_units"] == "LUMENS" else 4.0 * math.pi)
    intensity = max(2.0, min(10.0, 4.0 * math.sqrt(lumens / 200.0)))
    return [round(v / peak, 3) for v in raw], round(intensity * 2.0) / 2.0


def _body_names(source_mesh, parent, colour, intensity):
    mi_key = _canonical({"parent": parent, "colour": colour, "intensity": intensity})
    mi = "%s/MI_PB_Bulb_%s" % (BODY_ASSET_DIR, hashlib.sha1(mi_key.encode()).hexdigest()[:8])
    mesh_key = _canonical({"source": source_mesh, "material": mi})
    return mi, "%s/SM_PB_Bulb_%s" % (BODY_ASSET_DIR, hashlib.sha1(mesh_key.encode()).hexdigest()[:8])


def validate_body_material(row, where):
    spec = row.get("visible_mesh", {}).get("material")
    if spec is None:
        return
    require(isinstance(spec, dict) and set(spec) == {"parent", "mode"} and spec["parent"] in BODY_PARENTS
            and spec["mode"] in ("MATCH_LIGHT", "DIM"), "BAD_BODY_MATERIAL|" + where)
    require(row["role"] == "PRACTICAL" and str(row["visible_mesh"]["mesh"]).startswith(("/Engine/BasicShapes/", "/Game/")),
            "BAD_BODY_MATERIAL_HOST|" + where)
    require(bool(row["visible_mesh"]["emissive"]), "BODY_EMISSIVE_FLAG_DISAGREES|" + where)


def _resolve_lamp_bodies(fixtures, where):
    """Give each PRACTICAL_BODY prop of a light with visible_mesh.material its derived mesh, after every
    per-bay override, so a lamp switched off in a bay can never keep a glowing body (and vice versa)."""
    lights = {row["slot"]: row for row in fixtures if row.get("authored_kind") == "LIGHT"}
    for prop in fixtures:
        if prop.get("role") != "PRACTICAL_BODY":
            continue
        light = lights[prop["paired_slot"]]
        spec = light.get("visible_mesh", {}).get("material")
        if spec is None:
            continue
        here = "%s|slot=%s" % (where, light["slot"])
        validate_body_material(light, here)
        lumens = float(light["intensity"])
        require(lumens > 0.0, "BODY_GLOWS_ON_DEAD_LAMP|" + here)
        if spec["mode"] == "DIM":
            require(light["intensity_units"] == "LUMENS" and lumens <= DIM_MAX_LUMENS + 1.0e-9
                    and float(light["attenuation_cm"]) <= DIM_MAX_ATTENUATION_CM,
                    "BODY_DIM_ON_BRIGHT_LAMP|%s|lm=%.1f|att=%.0f" % (here, lumens, float(light["attenuation_cm"])))
        colour, intensity = body_emission(light, spec["mode"])
        mi, mesh = _body_names(prop["mesh"], spec["parent"], colour, intensity)
        prop["body"] = {"source_mesh": prop["mesh"], "parent": spec["parent"], "mode": spec["mode"],
                        "colour": colour, "intensity": intensity, "mi": mi, "mesh": mesh,
                        "flicker_follows_light": False}
        prop["mesh"] = mesh


def body_asset_plan(fixture_rows):
    """Unique derived assets a set of fixtures needs: {"mis": {path: spec}, "meshes": {path: spec}}."""
    mis, meshes = {}, {}
    for row in fixture_rows:
        body = row.get("body")
        if not body:
            continue
        mi = {"parent": body["parent"], "colour": body["colour"], "intensity": body["intensity"]}
        require(mis.setdefault(body["mi"], mi) == mi, "BODY_MI_NAME_COLLISION|" + body["mi"])
        mesh = {"source": body["source_mesh"], "material": body["mi"]}
        require(meshes.setdefault(body["mesh"], mesh) == mesh, "BODY_MESH_NAME_COLLISION|" + body["mesh"])
    for path in list(mis) + list(meshes):
        require(path.startswith(BODY_ASSET_DIR + "/"), "BODY_ASSET_OUTSIDE_DIR|" + path)
    return {"mis": mis, "meshes": meshes}


def _close_list(a, b, tol=1.0e-3):
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def ensure_body_assets(api, assets):
    """CREATE-ONLY. api: exists/read_mi/create_mi/read_mesh/create_mesh/save. Returns the created paths.
    An existing asset must already hold the planned values (read back), or the run stops: never edit it."""
    created = []
    for path, spec in sorted(assets["mis"].items()):
        if api.exists(path):
            got = api.read_mi(path)
            require(got["parent"] == spec["parent"] and _close_list(got["colour"][:3], spec["colour"])
                    and abs(float(got["intensity"]) - spec["intensity"]) <= 1.0e-3,
                    "BODY_ASSET_EXISTS_DIFFERENT|%s|have=%s|want=%s" % (path, _canonical(got), _canonical(spec)))
            continue
        api.create_mi(path, spec["parent"], spec["colour"], spec["intensity"])
        created.append(path)
        got = api.read_mi(path)
        require(got["parent"] == spec["parent"] and _close_list(got["colour"][:3], spec["colour"])
                and abs(float(got["intensity"]) - spec["intensity"]) <= 1.0e-3,
                "BODY_MI_READBACK|%s|%s" % (path, _canonical(got)))
    for path, spec in sorted(assets["meshes"].items()):
        if api.exists(path):
            got = api.read_mesh(path)
            require(got == spec, "BODY_ASSET_EXISTS_DIFFERENT|%s|have=%s|want=%s" % (path, _canonical(got), _canonical(spec)))
            continue
        api.create_mesh(path, spec["source"], spec["material"])
        created.append(path)
        require(api.read_mesh(path) == spec, "BODY_MESH_READBACK|" + path)
    for path in created:
        require(api.save(path), "BODY_ASSET_SAVE_FAILED|" + path)
    return created


def revert_body_assets(api, created, referenced):
    """Delete only assets this record created and nothing still references (another passage may share one:
    names are content hashes). Meshes before MIs. Returns {"deleted": [...], "kept_referenced": [...]}."""
    deleted, kept = [], []
    referenced = set(referenced)
    meshes = [p for p in created if "/SM_PB_Bulb_" in p]
    mis = [p for p in created if "/MI_PB_Bulb_" in p]
    require(len(meshes) + len(mis) == len(created) and all(p.startswith(BODY_ASSET_DIR + "/") for p in created),
            "BODY_REVERT_UNKNOWN_ASSET|" + _canonical(created))
    for path in meshes:
        if path in referenced or not api.exists(path):
            kept.append(path)
            continue
        require(api.delete(path), "BODY_ASSET_DELETE_FAILED|" + path)
        deleted.append(path)
    used_mis = {api.read_mesh(p)["material"] for p in api.list_meshes(BODY_ASSET_DIR) if api.exists(p)}
    for path in mis:
        if path in referenced or path in used_mis or not api.exists(path):
            kept.append(path)
            continue
        require(api.delete(path), "BODY_ASSET_DELETE_FAILED|" + path)
        deleted.append(path)
    return {"deleted": deleted, "kept_referenced": kept}


class UnrealBodyAssets:
    """The Unreal side of ensure/revert_body_assets (runs only in the editor; first exercised by a live APPLY,
    so every call below is INFERRED until then: MaterialEditingLibrary MI setters/getters and
    EditorAssetLibrary duplicate/save/delete are the same calls underpass_tubes_apply.py:85-99 uses live;
    StaticMesh.set_material/get_material are UE5 Python API, not yet run in this project)."""

    def __init__(self):
        self.eal = unreal.EditorAssetLibrary
        self.mel = unreal.MaterialEditingLibrary
        self.tools = unreal.AssetToolsHelpers.get_asset_tools()

    def exists(self, path):
        return bool(self.eal.does_asset_exist(path))

    def read_mi(self, path):
        mi = unreal.load_asset(path)
        names = BODY_PARENTS.get(mi.get_editor_property("parent").get_path_name().split(".")[0], ("Colour", "Intensity"))
        colour = self.mel.get_material_instance_vector_parameter_value(mi, names[0])
        return {"parent": mi.get_editor_property("parent").get_path_name().split(".")[0],
                "colour": [colour.r, colour.g, colour.b],
                "intensity": self.mel.get_material_instance_scalar_parameter_value(mi, names[1])}

    def create_mi(self, path, parent, colour, intensity):
        folder, name = path.rsplit("/", 1)
        mi = self.tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                                     unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "BODY_MI_CREATE_FAILED|" + path)
        names = BODY_PARENTS[parent]
        self.mel.set_material_instance_parent(mi, unreal.load_asset(parent))
        self.mel.set_material_instance_vector_parameter_value(mi, names[0], unreal.LinearColor(*(list(colour) + [1.0])))
        self.mel.set_material_instance_scalar_parameter_value(mi, names[1], float(intensity))

    def read_mesh(self, path):
        mesh = unreal.load_asset(path)
        material = mesh.get_material(0)
        return {"source": str(self.eal.get_metadata_tag(mesh, "PussBodySource")),
                "material": material.get_path_name().split(".")[0] if material else None}

    def create_mesh(self, path, source, material):
        mesh = self.eal.duplicate_asset(source, path)
        require(mesh is not None, "BODY_MESH_DUPLICATE_FAILED|" + path)
        mesh.set_material(0, unreal.load_asset(material))
        self.eal.set_metadata_tag(mesh, "PussBodySource", source)

    def save(self, path):
        return bool(self.eal.save_asset(path, only_if_is_dirty=False))

    def delete(self, path):
        return bool(self.eal.delete_asset(path))

    def list_meshes(self, folder):
        return [p.split(".")[0] for p in self.eal.list_assets(folder, recursive=False) if "/SM_PB_Bulb_" in p]


# --------------------------------------------------------------------------
# New light-function instances (6 Oct round 2): irregular ~1 Hz pulse, 2 Hz x ~0.5 s bursts (three phases, so
# lamps sharing a bay never burst together), harp flutter. CREATE-ONLY MaterialInstanceConstants of the existing
# M_LF_StageFlicker (scalar parameters only; no node is touched: the parent's graph is
# Saved/CodexLighting/rebuild_flicker_master.py:16-39). Declared in scores["flicker_instances"].
# lf_level() is that graph in Python (UE Sine node Period left at its default 1 -> sin(2*pi*x): Speed is Hz,
# Phase is cycles; INFERRED from the script, which never sets Period).
# --------------------------------------------------------------------------
FLICKER_PARENT = "/Game/InfinityStage/Lighting/M_LF_StageFlicker"
FLICKER_PARAMS = ("Speed", "SpeedRatio", "Depth", "Phase", "Hardness", "OnBias")


def lf_level(t, params):
    """M_LF_StageFlicker output at time t (1 = full, 1-Depth = fully dipped)."""
    sp, ra, de, ph, ha, ob = [float(params[name]) for name in FLICKER_PARAMS]
    s = 0.5 + 0.25 * math.sin(2.0 * math.pi * (sp * t + ph)) + 0.25 * math.sin(2.0 * math.pi * (sp * ra * t + 1.7 * ph))
    w = 0.5 * (1.0 - ha) + 0.002
    x = min(1.0, max(0.0, (s - (ob - w)) / (2.0 * w)))
    return 1.0 - de * (1.0 - x * x * (3.0 - 2.0 * x))


def validate_flicker_instances(scores):
    out = {}
    for path, spec in sorted(scores.get("flicker_instances", {}).items()):
        require(path.startswith(FLICKER_ROOT) and spec.get("parent") == FLICKER_PARENT
                and set(spec.get("params", {})) == set(FLICKER_PARAMS)
                and all(math.isfinite(float(v)) for v in spec["params"].values())
                and 0.0 <= float(spec["params"]["Depth"]) <= 1.0 and 0.0 <= float(spec["params"]["Hardness"]) <= 1.0,
                "BAD_FLICKER_INSTANCE|" + path)
        out[path] = {"parent": spec["parent"], "params": {k: float(v) for k, v in spec["params"].items()}}
    return out


def ensure_flicker_instances(api, wanted):
    """CREATE-ONLY, as ensure_body_assets. api: exists/read_lf/create_lf/save. Returns created paths."""
    created = []

    def same(got, spec):
        return got["parent"] == spec["parent"] and all(
            abs(float(got["params"].get(k, float("nan"))) - v) <= 1.0e-4 for k, v in spec["params"].items())
    for path, spec in sorted(wanted.items()):
        if api.exists(path):
            got = api.read_lf(path)
            require(same(got, spec), "FLICKER_INSTANCE_EXISTS_DIFFERENT|%s|have=%s|want=%s"
                    % (path, _canonical(got), _canonical(spec)))
            continue
        api.create_lf(path, spec["parent"], spec["params"])
        created.append(path)
        require(same(api.read_lf(path), spec), "FLICKER_INSTANCE_READBACK|" + path)
    for path in created:
        require(api.save(path), "FLICKER_INSTANCE_SAVE_FAILED|" + path)
    return created


class UnrealFlickerInstances:
    """Unreal side of ensure_flicker_instances. INFERRED until the first live APPLY: the same
    MaterialEditingLibrary scalar setters rebuild_flicker_master.py:48-52 ran live on 18 Sep."""

    def __init__(self):
        self.eal = unreal.EditorAssetLibrary
        self.mel = unreal.MaterialEditingLibrary
        self.tools = unreal.AssetToolsHelpers.get_asset_tools()

    def exists(self, path):
        return bool(self.eal.does_asset_exist(path))

    def read_lf(self, path):
        mi = unreal.load_asset(path)
        return {"parent": mi.get_editor_property("parent").get_path_name().split(".")[0],
                "params": {k: float(self.mel.get_material_instance_scalar_parameter_value(mi, k)) for k in FLICKER_PARAMS}}

    def create_lf(self, path, parent, params):
        folder, name = path.rsplit("/", 1)
        mi = self.tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                                     unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "FLICKER_INSTANCE_CREATE_FAILED|" + path)
        self.mel.set_material_instance_parent(mi, unreal.load_asset(parent))
        for key in FLICKER_PARAMS:
            self.mel.set_material_instance_scalar_parameter_value(mi, key, float(params[key]))
        self.mel.update_material_instance(mi)

    def save(self, path):
        return bool(self.eal.save_asset(path, only_if_is_dirty=False))


def bay_output(fixtures):
    """Scored light per bay. 6 Oct: DIM bulbs (dead bulbs revived at a fixed ~18 lm glow) are set dressing, not
    score output, so they do not count: a VOID bay with a glowing dead bulb is still 'dark' for the shape rules."""
    out = {unit: 0.0 for unit in UNITS}
    for row in fixtures:
        if row.get("authored_kind") == "LIGHT" and not row.get("dim_bulb"):
            out[row["intensity_units"]] += float(row["intensity"])
    return out


def _is_lit(output):
    return any(value > 0.0 for value in output.values())


def _is_pool(fixtures):
    """A lit POOL: some non-practical lamp emits. Practical-only bays are gaps."""
    return any(row.get("authored_kind") == "LIGHT" and row["role"] != "PRACTICAL"
               and float(row["intensity"]) > 0.0 for row in fixtures)


def check_score_shape(passage_key, passage, bay_rows):
    """Pools-and-gaps and monotone-dark rules over the expanded score."""
    exempt = set()
    for first, last in passage.get("max_consecutive_lit_exempt", []):
        exempt.update(range(int(first), int(last) + 1))
    limit = int(passage["max_consecutive_lit"])
    run = 0
    for row in bay_rows:
        if row["ordinal"] in exempt or not row["lit"]:
            run = 0
            continue
        run += 1
        require(run <= limit, "WASHED_OUT_RUN|passage=%s|bay=%d|run=%d|limit=%d"
                % (passage_key, row["ordinal"], run, limit))
    segment = passage.get("monotone_dark_segment")
    if segment:
        first, last = [int(v) for v in segment]
        rows = [row for row in bay_rows if first <= row["ordinal"] <= last]
        require(len(rows) == last - first + 1, "MONOTONE_SEGMENT_INCOMPLETE|passage=" + passage_key)
        for previous, current in zip(rows, rows[1:]):
            for unit in UNITS:
                require(current["output"][unit] <= previous["output"][unit] + 1.0e-9,
                        "NOT_MONOTONE_DARK|passage=%s|bay=%d|unit=%s|%.6f>%.6f"
                        % (passage_key, current["ordinal"], unit,
                           current["output"][unit], previous["output"][unit]))
            require(not _is_lit(current["output"])
                    or current["stutter"] + 1.0e-12 >= previous["stutter"],
                    "STUTTER_NOT_RISING|passage=%s|bay=%d" % (passage_key, current["ordinal"]))
        require(not _is_lit(rows[-1]["output"]),
                "MONOTONE_SEGMENT_NOT_DARK_AT_END|passage=%s|bay=%d" % (passage_key, last))


def validate_scores(scores, looks, tool):
    """Static validation of every passage (no Show needed). Returns per-passage specs."""
    require(scores.get("schema_version") == 1, "SCORES_SCHEMA_NOT_1")
    require(scores.get("existing_light_policy") == "disable_all_in_target_bay_except_retained",
            "EXISTING_LIGHT_POLICY_UNSAFE")
    _check_drama({k: v for k, v in scores["distance_keying_default"].items() if k != "mechanism"},
                 "default")
    require(scores["distance_keying_default"].get("mechanism")
            == "FInfinityStageLightDrama strike-on-approach", "DISTANCE_MECHANISM_WRONG")
    check_foreign_owned_rules(scores)
    forbidden = set(scores.get("forbidden_looks", []))
    out = {}
    for passage_key, passage in sorted(scores["passages"].items()):
        require(PASSAGE_KEY.match(passage_key), "BAD_PASSAGE_KEY|" + passage_key)
        require(passage.get("shadow_policy") in SHADOW_POLICIES, "BAD_SHADOW_POLICY|" + passage_key)
        specs = expand_score(passage_key, passage)
        cross_cfg = no_cross_config(passage)
        cross_rows = []
        rows = []
        prototype_range = set()
        if passage.get("prototype"):
            first, last = passage["prototype"]["bays"]
            prototype_range = set(range(int(first), int(last) + 1))
        for spec in specs:
            look = spec["look"]
            if look == "PROTOTYPE":
                require(spec["ordinal"] in prototype_range,
                        "PROTOTYPE_BAY_UNDECLARED|passage=%s|bay=%d" % (passage_key, spec["ordinal"]))
                fallback = spec.get("if_absent")
                require(isinstance(fallback, dict) and fallback.get("look") in looks
                        and fallback["look"] not in forbidden,
                        "PROTOTYPE_FALLBACK_BAD|passage=%s|bay=%d" % (passage_key, spec["ordinal"]))
                rows.append({"ordinal": spec["ordinal"], "look": "PROTOTYPE", "lit": True,
                             "output": {u: float("nan") for u in UNITS}, "stutter": 0.0})
                continue
            require(spec["ordinal"] not in prototype_range,
                    "PROTOTYPE_BAY_SCORED|passage=%s|bay=%d" % (passage_key, spec["ordinal"]))
            require(look not in forbidden, "FORBIDDEN_LOOK|passage=%s|bay=%d|look=%s"
                    % (passage_key, spec["ordinal"], look))
            require(look in looks, "UNKNOWN_LOOK|passage=%s|bay=%d|look=%s"
                    % (passage_key, spec["ordinal"], look))
            fixtures = bay_fixtures(tool, scores, looks, passage_key, spec)
            if cross_cfg is not None:
                cross_rows.extend(no_cross_rows(passage_key, spec["ordinal"], fixtures, cross_cfg))
            output = bay_output(fixtures)
            rows.append({"ordinal": spec["ordinal"], "look": look, "lit": _is_pool(fixtures),
                         "output": output,
                         "stutter": float(spec["drama"].get("ignition_stutter", 0.0))})
        check_score_shape(passage_key, passage, rows)
        for rule in passage.get("retain", []):
            require(isinstance(rule.get("label_suffix"), str) and rule["label_suffix"].startswith(" ")
                    and int(rule.get("expected_count", 0)) >= 1
                    and (rule.get("scope") == "passage" or isinstance(rule.get("bay"), int)),
                    "BAD_RETAIN_RULE|passage=" + passage_key)
        for key, guid in passage.get("pinned_cue_guids", {}).items():
            require(1 <= int(key) <= int(passage["expected_bay_count"])
                    and re.match(r"^[0-9A-F]{32}$", guid), "BAD_PIN|passage=%s|bay=%s" % (passage_key, key))
        yield_cfg = passage.get("yield_to_events")
        if yield_cfg is not None:
            first, last = [int(v) for v in yield_cfg["bays"]]
            require(1 <= first <= last <= int(yield_cfg["layout_bay_count"])
                    and str(yield_cfg.get("owner", "")).strip(), "BAD_YIELD|passage=" + passage_key)
        out[passage_key] = {"specs": specs, "rows": rows,
                            "no_cross": None if cross_cfg is None else {"config": cross_cfg, "rows": cross_rows}}
    return out


# --------------------------------------------------------------------------
# Plain (offline-testable) Show model and plan.
#   cue:     {"show_index", "guid", "label", "type": "WING_PAIR"|..., "attachments": [...]}
#   attach:  {"guid", "label", "kind": "Light"|..., "enabled", "lighting": {"cast_shadows"}}
#   passage: {"label", "guid", "first_cue_guid", "last_cue_guid"}
# --------------------------------------------------------------------------
def _is_wing_pair(cue):
    return "WING_PAIR" in str(cue.get("type", "")).upper().replace(" ", "_")


def resolve_passage_bays(passages, cues, passage_label):
    """Ordinal -> cue rows for the WingPair cues in one PassageSettings range.

    Mirrors UInfinityStageShowAsset::GetWingPairCueGuidsInPassage
    (InfinityStageShowAsset.cpp:496-521): first..last by Show index, WingPair only.
    """
    matches = [row for row in passages if row["label"] == passage_label]
    require(len(matches) == 1, "PASSAGE_ROW_COUNT|label=%s|count=%d" % (passage_label, len(matches)))
    passage = matches[0]
    guids = [str(cue["guid"]) for cue in cues]
    require(all(guids) and len(guids) == len(set(guids)), "CUE_GUIDS_INVALID_OR_DUPLICATE")
    index = {guid: position for position, guid in enumerate(guids)}
    require(passage["first_cue_guid"] in index and passage["last_cue_guid"] in index,
            "PASSAGE_RANGE_UNRESOLVED|label=" + passage_label)
    first, last = index[passage["first_cue_guid"]], index[passage["last_cue_guid"]]
    require(first <= last, "PASSAGE_RANGE_INVERTED|label=" + passage_label)
    rows = []
    for position in range(first, last + 1):
        cue = cues[position]
        if _is_wing_pair(cue):
            rows.append({"ordinal": len(rows) + 1, "show_index": position,
                         "cue_guid": str(cue["guid"]), "cue_label": str(cue["label"])})
    return passage, rows


def prototype_state(passage_cfg, bay_rows, cues_by_guid, record):
    """Classify the P04 prototype as APPLIED / ABSENT / MIXED (GUID-keyed)."""
    proto = passage_cfg.get("prototype")
    if not proto:
        return {"state": "NONE", "owned_guids": []}
    first, last = [int(v) for v in proto["bays"]]
    declared = {row["cue_guid"] for row in bay_rows if first <= row["ordinal"] <= last}
    passage_guids = {row["cue_guid"] for row in bay_rows}
    labelled = {guid for guid in passage_guids
                if any(str(att.get("label", "")).startswith(proto["label_prefix"])
                       for att in cues_by_guid[guid]["attachments"])}
    record_guids = set()
    record_status = None
    if record is not None:
        record_status = record.get("status")
        record_guids = set(record.get("plan", {}).get("target_cue_guids", []))
    if (record_status == "saved_readback_verified" and record_guids == declared
            and labelled == declared):
        state = "APPLIED"
    elif record is None and not labelled:
        state = "ABSENT"
    else:
        state = "MIXED"
    return {"state": state, "declared_guids": sorted(declared), "labelled_guids": sorted(labelled),
            "record_guids": sorted(record_guids), "record_status": record_status,
            "owned_guids": sorted(declared) if state == "APPLIED" else []}


def check_foreign_owned_rules(scores):
    """Lamps another tool owns (scores["foreign_owned_lights"]) must each be a retain rule with the same
    bay, suffix and owner in their passage, so this tool never disables or edits them. Added 4 Oct for the
    P01 house warmers (Gary: off for the Opening ONLY, on in P01; owner opening_sequence_apply.py)."""
    for rule in scores.get("foreign_owned_lights", []):
        key = rule.get("passage")
        require(key in scores["passages"] and isinstance(rule.get("bay"), int)
                and str(rule.get("label_suffix", "")).startswith(" ") and str(rule.get("owner", "")).strip(),
                "BAD_FOREIGN_OWNED|" + _canonical(rule))
        match = [r for r in scores["passages"][key].get("retain", [])
                 if r.get("bay") == rule["bay"] and r.get("label_suffix") == rule["label_suffix"]
                 and r.get("owner") == rule["owner"]]
        require(len(match) == 1, "FOREIGN_OWNED_NOT_RETAINED|passage=%s|bay=%s|suffix=%r|owner=%s|matches=%d"
                % (key, rule["bay"], rule["label_suffix"], rule["owner"], len(match)))


def check_foreign_owned_retained(scores, passage_key, retain_report):
    """Run-time half: every foreign-owned lamp in this passage resolved to a retained attachment."""
    report = []
    for rule in scores.get("foreign_owned_lights", []):
        if rule.get("passage") != passage_key:
            continue
        hits = [r for r in retain_report if r["bay"] == rule["bay"] and r["label"].endswith(rule["label_suffix"])]
        require(len(hits) >= 1, "FOREIGN_OWNED_NOT_RETAINED_LIVE|passage=%s|bay=%s|suffix=%r"
                % (passage_key, rule["bay"], rule["label_suffix"]))
        report.extend(dict(hit, owner=rule["owner"]) for hit in hits)
    return report


def match_retains(passage_key, passage_cfg, target_rows, cues_by_guid):
    retained = {}
    report = []
    for rule in passage_cfg.get("retain", []):
        if rule.get("scope") == "passage":
            scope = target_rows
        else:
            scope = [row for row in target_rows if row["ordinal"] == int(rule["bay"])]
            require(len(scope) == 1, "RETAIN_BAY_NOT_TARGET|passage=%s|bay=%s" % (passage_key, rule["bay"]))
        hits = []
        for row in scope:
            for att in cues_by_guid[row["cue_guid"]]["attachments"]:
                if str(att.get("kind", "")).upper() == "LIGHT" and str(att.get("label", "")).endswith(rule["label_suffix"]):
                    hits.append((row["cue_guid"], str(att["guid"]), str(att["label"]), row["ordinal"]))
        require(len(hits) == int(rule["expected_count"]),
                "RETAIN_COUNT|passage=%s|suffix=%r|expected=%d|actual=%d|hits=%s"
                % (passage_key, rule["label_suffix"], int(rule["expected_count"]), len(hits),
                   [hit[2] for hit in hits]))
        for cue_guid, att_guid, label, ordinal in hits:
            require(att_guid not in retained.get(cue_guid, {}), "RETAIN_OVERLAP|guid=" + att_guid)
            retained.setdefault(cue_guid, {})[att_guid] = label
            report.append({"bay": ordinal, "cue_guid": cue_guid, "guid": att_guid, "label": label})
    return retained, report


def yield_state(passage_cfg, bay_rows):
    """Bays this score YIELDS to lighting_events_apply.py (black mode; Gary 4 Oct).

    The yield is keyed to a bay LAYOUT: ordinals mean something only for the
    cue count they were decided on (P06 bays 2-10 of the 64-cue post-interleave
    layout). On any other count the yield is DORMANT and the score keeps those
    bays (today P06 has 55 cues, so the score is unchanged until it is rescored
    to 64, when the yield becomes ACTIVE)."""
    cfg = passage_cfg.get("yield_to_events")
    if not cfg:
        return {"state": "NONE", "ordinals": [], "cue_guids": []}
    first, last = [int(v) for v in cfg["bays"]]
    if int(cfg["layout_bay_count"]) != len(bay_rows):
        return {"state": "DORMANT", "layout_bay_count": int(cfg["layout_bay_count"]),
                "actual_bay_count": len(bay_rows), "ordinals": [], "cue_guids": []}
    ordinals = list(range(first, last + 1))
    return {"state": "ACTIVE", "owner": cfg["owner"], "ordinals": ordinals,
            "cue_guids": [bay_rows[o - 1]["cue_guid"] for o in ordinals]}


def _apply_shadow_policy(policy, targets):
    lit_index = 0
    for target in targets:
        casters = [row for row in target["fixtures"]
                   if row["authored_kind"] == "LIGHT" and row.get("cast_shadows")]
        if policy == "NONE":
            keep = False
        elif policy == "ALTERNATE_LIT":
            keep = bool(casters) and lit_index % 2 == 0
            if casters:
                lit_index += 1
        else:
            keep = True
        if not keep:
            for row in casters:
                row["cast_shadows"] = False


def build_score_plan(tool, scores, looks, passage_key, passages, cues, p04_record=None,
                     prototype_absent=None):
    """Resolve the passage's bays by GUID and prove scope, ownership and budget."""
    require(PASSAGE_KEY.match(str(passage_key)), "BAD_PASSAGE|passage=%s" % passage_key)
    require(passage_key in scores["passages"], "PASSAGE_NOT_SCORED|passage=" + passage_key)
    static = validate_scores(scores, looks, tool)[passage_key]
    passage_cfg = scores["passages"][passage_key]
    passage_row, bay_rows = resolve_passage_bays(passages, cues, passage_cfg["passage_label"])
    require(len(bay_rows) == int(passage_cfg["expected_bay_count"]),
            "BAY_COUNT_DRIFT|passage=%s|expected=%d|actual=%d|rescore_before_apply"
            % (passage_key, int(passage_cfg["expected_bay_count"]), len(bay_rows)))
    for key, guid in passage_cfg.get("pinned_cue_guids", {}).items():
        actual = bay_rows[int(key) - 1]["cue_guid"]
        require(actual == guid, "PINNED_GUID_DRIFT|passage=%s|bay=%s|pinned=%s|actual=%s"
                % (passage_key, key, guid, actual))
    guard = re.compile(passage_cfg["cue_label_drift_guard"])
    drift = [row["cue_label"] for row in bay_rows if not guard.match(row["cue_label"])]
    require(not drift, "CUE_LABEL_DRIFT|passage=%s|labels=%s" % (passage_key, drift[:5]))
    cues_by_guid = {str(cue["guid"]): cue for cue in cues}

    proto = prototype_state(passage_cfg, bay_rows, cues_by_guid, p04_record)
    if passage_cfg.get("prototype"):
        require(proto["state"] != "MIXED", "PROTOTYPE_STATE_MIXED|%s" % _canonical(proto))
        if proto["state"] == "ABSENT":
            require(prototype_absent == "AUTHOR_FALLBACK",
                    "PROTOTYPE_ABSENT|the P04 score expects lighting_looks_apply.py to own bays %s;"
                    " run after the prototype is applied, or pass"
                    " LIGHTING_SCORES_PROTOTYPE_ABSENT='AUTHOR_FALLBACK'" % passage_cfg["prototype"]["bays"])
    owned = set(proto["owned_guids"])
    yielded = yield_state(passage_cfg, bay_rows)
    yielded_ordinals = set(yielded["ordinals"])

    prefix = scores["fixture_label_prefix_format"] % int(passage_key[1:])
    present = sorted({cue["guid"] for cue in cues for att in cue["attachments"]
                      if str(att.get("label", "")).startswith(prefix + " ")})
    require(not present, "SCORE_ALREADY_PRESENT|passage=%s|cues=%s" % (passage_key, present))

    targets = []
    skipped = []
    for spec, row in zip(static["specs"], bay_rows):
        require(spec["ordinal"] == row["ordinal"], "ORDINAL_MISMATCH")
        if row["ordinal"] in yielded_ordinals:
            skipped.append({"bay": row["ordinal"], "cue_guid": row["cue_guid"],
                            "cue_label": row["cue_label"], "owner": yielded["owner"]})
            continue
        if spec["look"] == "PROTOTYPE":
            if row["cue_guid"] in owned:
                skipped.append({"bay": row["ordinal"], "cue_guid": row["cue_guid"],
                                "cue_label": row["cue_label"], "owner": "lighting_looks_apply.py"})
                continue
            spec = dict(spec)
            spec.update({"look": spec["if_absent"]["look"],
                         "level": float(spec["if_absent"].get("level", 1.0)),
                         "mirror": list(spec["if_absent"].get("mirror", [])),
                         "note": "prototype fallback (prototype ABSENT, AUTHOR_FALLBACK)"})
        fixtures = bay_fixtures(tool, scores, looks, passage_key, spec)
        cpp_pending = spec.get("cpp_pending", [])
        cue = cues_by_guid[row["cue_guid"]]
        lights = [att for att in cue["attachments"] if str(att.get("kind", "")).upper() == "LIGHT"]
        targets.append({
            "bay_index": row["ordinal"],
            "ordinal": row["ordinal"],
            "look": spec["look"],
            "level_scale": spec["level"],
            "drama": copy.deepcopy(spec["drama"]),
            "drop_slots": list(spec["drop_slots"]),
            "show_index": row["show_index"],
            "cue_label": row["cue_label"],
            "cue_guid": row["cue_guid"],
            "existing_lights": len(lights),
            "fixtures": fixtures,
            "fixture_count": len(fixtures),
            "light_fixture_count": sum(f["authored_kind"] == "LIGHT" for f in fixtures),
            "practical_prop_count": sum(f["authored_kind"] == "PROP" for f in fixtures),
            "cpp_pending": cpp_pending,
        })
    require(len({t["cue_guid"] for t in targets}) == len(targets), "TARGET_GUIDS_NOT_UNIQUE")
    cross_cfg = no_cross_config(passage_cfg)
    cross = None
    if cross_cfg is not None:
        cross = {"config": cross_cfg, "static": [row for t in targets for row in
                                                  no_cross_rows(passage_key, t["ordinal"], t["fixtures"], cross_cfg)],
                 "live": None}

    retained, retain_report = match_retains(passage_key, passage_cfg, targets, cues_by_guid)
    foreign_report = check_foreign_owned_retained(scores, passage_key, retain_report)
    _apply_shadow_policy(passage_cfg["shadow_policy"], targets)
    for target in targets:
        cue = cues_by_guid[target["cue_guid"]]
        keep = retained.get(target["cue_guid"], {})
        lights = [att for att in cue["attachments"] if str(att.get("kind", "")).upper() == "LIGHT"]
        target["retained_guids"] = sorted(keep)
        target["existing_shadow_casters"] = sum(tool._plain_casts(att) for att in lights)
        target["removed_shadow_casters"] = sum(tool._plain_casts(att) for att in lights
                                               if str(att["guid"]) not in keep)
        target["disabled_lights"] = sum(1 for att in lights
                                        if str(att["guid"]) not in keep and bool(att.get("enabled", True)))
        target["new_shadow_casters"] = sum(bool(f.get("cast_shadows")) for f in target["fixtures"]
                                           if f["authored_kind"] == "LIGHT")
        target["output"] = bay_output(target["fixtures"])

    labels = [f["label"] for t in targets for f in t["fixtures"]]
    require(len(labels) == len(set(labels)), "NEW_LABELS_DUPLICATE")
    existing_labels = {str(att.get("label", "")) for cue in cues for att in cue["attachments"]}
    clashes = sorted(existing_labels.intersection(labels))
    require(not clashes, "LABEL_CLASH|labels=" + ",".join(clashes[:5]))

    passage_guids = {row["cue_guid"] for row in bay_rows}
    before = sum(tool._plain_casts(att) for guid in passage_guids
                 for att in cues_by_guid[guid]["attachments"])
    removed = sum(t["removed_shadow_casters"] for t in targets)
    added = sum(t["new_shadow_casters"] for t in targets)
    after = before - removed + added
    require(after <= before, "SHADOW_BUDGET_EXCEEDED|passage=%s|before=%d|after=%d|removed=%d|added=%d"
            % (passage_key, before, after, removed, added))
    return {
        "passage": passage_key,
        "passage_label": passage_cfg["passage_label"],
        "passage_guid": passage_row["guid"],
        "bay_count": len(bay_rows),
        "bay_guids": [row["cue_guid"] for row in bay_rows],
        "prototype": proto,
        "yield_to_events": yielded,
        "skipped": skipped,
        "retained": retain_report,
        "foreign_owned": foreign_report,
        "targets": targets,
        "target_cue_guids": sorted(t["cue_guid"] for t in targets),
        "fixture_count": sum(t["fixture_count"] for t in targets),
        "light_fixture_count": sum(t["light_fixture_count"] for t in targets),
        "practical_prop_count": sum(t["practical_prop_count"] for t in targets),
        "existing_lights_disabled": sum(t["disabled_lights"] for t in targets),
        "shadow": {"passage_before": before, "passage_after": after, "target_before": removed,
                   "target_after": added,
                   "retained_casters": sum(t["existing_shadow_casters"] - t["removed_shadow_casters"]
                                           for t in targets),
                   "budget_ok": after <= before},
        "label_prefix": prefix,
        "no_cross": cross,
        "warnings": [p["warning"] for t in targets for p in t["cpp_pending"]],
    }


def plain_rows(cues):
    return {str(cue["guid"]): copy.deepcopy(cue["attachments"]) for cue in cues}


def plain_outside_hash(tool, cues, target_guids):
    return tool._outside_hash(plain_rows(cues), target_guids)


def apply_plain_state(plan, cues):
    """Offline model of the mutation (same scope rules as the Unreal path)."""
    result = copy.deepcopy(cues)
    by_guid = {str(cue["guid"]): cue for cue in result}
    record = {"targets": {}, "added": {}}
    for target in plan["targets"]:
        cue = by_guid[target["cue_guid"]]
        record["targets"][target["cue_guid"]] = copy.deepcopy(cue["attachments"])
        keep = set(target["retained_guids"])
        for att in cue["attachments"]:
            if str(att.get("kind", "")).upper() == "LIGHT" and str(att["guid"]) not in keep:
                att["enabled"] = False
        added = []
        for fixture in target["fixtures"]:
            guid = "NEW-%s-%02d-%s" % (plan["passage"], target["ordinal"], fixture["slot"])
            added.append(guid)
            cue["attachments"].append({
                "guid": guid, "label": fixture["label"],
                "kind": "Light" if fixture["authored_kind"] == "LIGHT" else "Prop",
                "enabled": True,
                "lighting": {"cast_shadows": bool(fixture.get("cast_shadows", False)),
                             "intensity": float(fixture.get("intensity", 0.0))},
            })
        record["added"][target["cue_guid"]] = added
        record.setdefault("after", {})[target["cue_guid"]] = copy.deepcopy(cue["attachments"])
    return result, record


def revert_plain_state(cues, record):
    result = copy.deepcopy(cues)
    by_guid = {str(cue["guid"]): cue for cue in result}
    require(set(record["targets"]).issubset(by_guid), "REVERT_TARGET_MISSING")
    for cue_guid, before in record["targets"].items():
        current = by_guid[cue_guid]["attachments"]
        require(_canonical(current) == _canonical(record["after"][cue_guid]),
                "REVERT_CURRENT_STATE_DRIFT|cue=" + cue_guid)
        by_guid[cue_guid]["attachments"] = copy.deepcopy(before)
    return result


def passage_casters(tool, cues, guids):
    by_guid = {str(cue["guid"]): cue for cue in cues}
    return sum(tool._plain_casts(att) for guid in guids for att in by_guid[guid]["attachments"])


# --------------------------------------------------------------------------
# Foreign active-record interlock (offline file scan).
# --------------------------------------------------------------------------
TERMINAL_STATUSES = {"reverted", "failed_rolled_back_in_memory", "stale", "superseded"}


def scan_foreign_records(roots, guids, exclude=()):
    """Active *record*.json files under ``roots`` that mention any target GUID."""
    wanted = {str(guid).upper() for guid in guids}
    excluded = {os.path.normcase(os.path.abspath(path)) for path in exclude}
    hits = []
    for root in roots:
        for path in sorted(glob.glob(os.path.join(root, "**", "*record*.json"), recursive=True)):
            normal = os.path.normcase(os.path.abspath(path))
            if normal in excluded or not path.endswith(".json"):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
            except OSError:
                continue
            try:
                status = str(json.loads(text).get("status", "")).lower()
            except (ValueError, AttributeError):
                status = ""
            if status in TERMINAL_STATUSES:
                continue
            compact = text.upper().replace("-", "")
            found = sorted(guid for guid in wanted if guid in compact)
            if found:
                hits.append({"path": path, "status": status or None, "guids": found,
                             "sha256": _sha256_bytes(text.encode("utf-8"))})
    return hits


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline).
# --------------------------------------------------------------------------
def _record_path(passage_key):
    return os.path.join(HERE, "lighting_scores_record_%s.json" % passage_key)


def _report_path(passage_key):
    return os.path.join(HERE, "lighting_scores_report_%s.json" % passage_key)


def _runtime_plain(tool, show):
    plain = tool._plain_cues(show)
    cues = list(show.get_editor_property("cues"))
    require(len(plain) == len(cues), "PLAIN_CUE_COUNT")
    for row, cue in zip(plain, cues):
        row["type"] = str(cue.get_editor_property("type")).upper()
    passages = []
    for settings in show.get_editor_property("passage_settings"):
        passages.append({
            "label": str(settings.get_editor_property("label")),
            "guid": tool._guid_text(settings.get_editor_property("passage_guid")),
            "first_cue_guid": tool._guid_text(settings.get_editor_property("first_cue_guid")),
            "last_cue_guid": tool._guid_text(settings.get_editor_property("last_cue_guid")),
        })
    return plain, passages


def _require_show_resolution(tool, show, plan):
    """Second, independent resolve: the Show's own passage query must agree."""
    passages = [s for s in show.get_editor_property("passage_settings")
                if tool._guid_text(s.get_editor_property("passage_guid")) == plan["passage_guid"]]
    require(len(passages) == 1, "PASSAGE_GUID_RESOLVE_COUNT|%d" % len(passages))
    guids = [tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(
        passages[0].get_editor_property("passage_guid"))]
    require(guids == plan["bay_guids"], "SHOW_PASSAGE_QUERY_DISAGREES|show=%d|plan=%d"
            % (len(guids), len(plan["bay_guids"])))


def _apply_live_aims(tool, show, plan):
    """Aim TOP slots at the live panel of their side, and explicit accents at
    live panel + pair-space offset (generalises lighting_looks_apply.py's
    _apply_live_top_aims to any TOP count, including failing bays)."""
    cues = list(show.get_editor_property("cues"))
    for target in plan["targets"]:
        pair = cues[target["show_index"]].get_editor_property("wing_pair")
        panels = {"L": pair.get_editor_property("left"), "R": pair.get_editor_property("right")}
        target["aims"] = []
        for fixture in target["fixtures"]:
            if fixture["authored_kind"] != "LIGHT":
                continue
            explicit = fixture.get("aim_wing_side")
            if fixture.get("aim_target_pair_cm") is not None:
                continue  # fixed look-at point, aimed offline in bay_fixtures
            if fixture["role"] != "TOP" and explicit is None:
                continue
            if explicit is None:
                side, offset = fixture["slot"].rsplit("_", 1)[-1], [0.0, 0.0, 0.0]
            else:
                side = "L" if explicit == "LEFT" else "R"
                offset = [float(v) for v in fixture["aim_offset_pair_cm"]]
            require(side in panels, "AIM_SIDE_UNKNOWN|fixture=" + fixture["label"])
            location = panels[side].get_editor_property("local_transform").translation
            goal = [float(location.x) + offset[0], float(location.y) + offset[1],
                    float(location.z) + offset[2]]
            source = [float(v) for v in fixture["transform"]["location_cm"]]
            fixture["transform"]["rotation_rpy_deg"] = tool._look_at_rpy(source, goal, fixture["label"])
            target["aims"].append({"fixture": fixture["label"], "panel": side, "target_cm": goal,
                                   "rotation_rpy_deg": fixture["transform"]["rotation_rpy_deg"]})


PASSAGE_TICKS_PER_SECOND = 24000.0  # Show TickResolution (run_p6.json tick_resolution 24000) [measured offline]


def beat_check(beat_map, pass_rows):
    """For each planned beat lamp: when does it actually strike, given LIVE per-bay pass times and distances?
    pass_rows: {ordinal: {"t_s": seconds from the first pass, "d_cm": cm from the first pass}}; beat_map rows:
    {"bay", "beat_s", "strike_distance_cm", "first_pass_s"}. Speed inside a bay is the bay's own gap/interval
    (InfinityStageCompiler.cpp:380-411 per passage_retime_to_music.py:14). REPORT ONLY."""
    out = []
    for row in beat_map:
        bay = int(row["bay"])
        here, before = pass_rows.get(bay), pass_rows.get(bay - 1)
        if here is None or before is None:
            out.append(dict(row, verdict="UNREADABLE"))
            continue
        span_s, span_cm = here["t_s"] - before["t_s"], here["d_cm"] - before["d_cm"]
        speed = span_cm / span_s if span_s > 0 else float("nan")
        strike_s = float(row["first_pass_s"]) + here["t_s"] - float(row["strike_distance_cm"]) / speed
        drift = strike_s - float(row["beat_s"])
        out.append(dict(row, live_strike_s=round(strike_s, 2), drift_s=round(drift, 2),
                        verdict="ON_BEAT" if abs(drift) <= 0.35 else "OFF_BEAT_RETUNE"))
    return out


def _passage_timing(tool, show, plan):
    """Per-bay pass time and distance relative to the FIRST bay of the passage, read from the wing pairs'
    IntervalToNext / GapToNextCm (property names as passage_retime_to_music.py:857-858 reads them). The lead-in is
    not read here: beat maps carry first_pass_s, which the DRY must confirm. Never refuses."""
    try:
        cues = list(show.get_editor_property("cues"))
        by_guid = {tool._guid_text(c.get_editor_property("cue_guid")): c for c in cues}
        rows, t, d = {}, 0.0, 0.0
        for ordinal, guid in enumerate(plan["bay_guids"], start=1):
            rows[ordinal] = {"t_s": round(t, 4), "d_cm": round(d, 2)}
            pair = by_guid[guid].get_editor_property("wing_pair")
            t += int(pair.get_editor_property("interval_to_next").value) / PASSAGE_TICKS_PER_SECOND
            d += float(pair.get_editor_property("gap_to_next_cm"))
        return {"ok": True, "rows": rows}
    except Exception as error:  # noqa: BLE001 - a readout, never a gate
        return {"ok": False, "error": "%s: %s" % (type(error).__name__, error)}


def require_no_cross_live(plan):
    """Re-run the no-cross rule on the LIVE panel goals _apply_live_aims wrote
    (plan.targets[].aims). Static validation used nominal panels; this is the
    run-time half, and it refuses DRY and APPLY alike."""
    if not plan.get("no_cross"):
        return None
    live = []
    for target in plan["targets"]:
        goals = {aim["fixture"]: aim["target_cm"] for aim in target.get("aims", [])}
        live.extend(no_cross_rows(plan["passage"], target["ordinal"], target["fixtures"],
                                  plan["no_cross"]["config"], goals))
    plan["no_cross"]["live"] = live
    return live


def _make_score_light(tool, row, materials):
    """P04 _make_light, then the drama fields it hard-codes (stutter) or omits."""
    attachment = tool._make_light(row, materials)
    keying = row["distance_keying"]
    settings = attachment.get_editor_property("lighting")
    drama = settings.get_editor_property("drama")
    drama.set_editor_property("ignition_stutter", float(keying.get("ignition_stutter", 0.0)))
    if "after_pass_distance_cm" in keying:
        drama.set_editor_property("after_pass_distance_cm", float(keying["after_pass_distance_cm"]))
    if "decay_distance_cm" in keying:
        drama.set_editor_property("decay_distance_cm", float(keying["decay_distance_cm"]))
    settings.set_editor_property("drama", drama)
    attachment.set_editor_property("lighting", settings)
    return attachment


def _template(tool, fixture, materials, meshes):
    if fixture["authored_kind"] == "LIGHT":
        return _make_score_light(tool, fixture, materials)
    return tool._make_prop(fixture, meshes)


def _assets(tool, looks, scores):
    """Flicker materials and practical meshes the templates need. A declared new flicker instance that does not
    exist yet is stood in by its parent for DRY templates (APPLY creates it before the mutation)."""
    config = {"looks": looks}
    declared = validate_flicker_instances(scores)
    flicker_state = {path: ("REUSE" if unreal.EditorAssetLibrary.does_asset_exist(path) else "CREATE")
                     for path in declared}
    paths = sorted({row["flicker"]["material"] for look in looks.values() for row in look["instruments"]
                    if row["flicker"]["material"]})
    materials = {}
    for path in paths:
        if flicker_state.get(path) == "CREATE":
            asset = unreal.load_asset(declared[path]["parent"])
        else:
            asset = unreal.load_asset(path)
        require(asset is not None, "FLICKER_MATERIAL_MISSING|asset=" + path)
        materials[path] = asset
    meshes = tool._practical_meshes(config)
    if scores.get("bulb_caps", {}).get("enabled"):
        cap = unreal.load_asset(CAP_MESH)
        require(cap is not None, "CAP_MESH_MISSING|" + CAP_MESH)
        meshes[CAP_MESH] = cap
    return materials, meshes, declared, flicker_state


def _current_target(tool, show, target):
    cues = list(show.get_editor_property("cues"))
    matches = [i for i, cue in enumerate(cues)
               if tool._guid_text(cue.get_editor_property("cue_guid")) == target["cue_guid"]]
    require(len(matches) == 1, "CUE_GUID_RESOLVE_COUNT|guid=%s|count=%d" % (target["cue_guid"], len(matches)))
    index = matches[0]
    require(index == target["show_index"], "TARGET_INDEX_DRIFT|guid=" + target["cue_guid"])
    require(str(cues[index].get_editor_property("label")) == target["cue_label"],
            "TARGET_LABEL_DRIFT|guid=" + target["cue_guid"])
    return index, tool._pair_attachments(cues[index])


def _choose_scratch(tool, show, plan, avoid):
    """A WingPair cue outside this passage's targets and the prototype; nearest first."""
    cues = list(show.get_editor_property("cues"))
    targets = (set(plan["target_cue_guids"]) | set(plan["prototype"].get("owned_guids", []))
               | set(plan.get("yield_to_events", {}).get("cue_guids", [])) | set(avoid))
    anchor = min(t["show_index"] for t in plan["targets"])
    candidates = []
    for index, cue in enumerate(cues):
        guid = tool._guid_text(cue.get_editor_property("cue_guid"))
        if guid in targets or "WING_PAIR" not in str(cue.get_editor_property("type")).upper():
            continue
        candidates.append((abs(index - anchor), index, guid))
    require(candidates, "SCRATCH_CUE_MISSING")
    candidates.sort()
    return candidates[0][1], candidates[0][2]


def _mutate_apply(tool, show, plan, materials, meshes, avoid):
    cues = list(show.get_editor_property("cues"))
    scratch_index, scratch_guid = _choose_scratch(tool, show, plan, avoid)
    plan["scratch"] = {"show_index": scratch_index, "cue_guid": scratch_guid}
    scratch_original = tool._pair_attachments(cues[scratch_index])
    scratch_before = tool._attachment_rows(scratch_original)
    scratch_lights = sum(tool._is_light(item) for item in scratch_original)
    needed = max(t["existing_lights"] + t["fixture_count"] for t in plan["targets"])
    padding = max(0, needed - scratch_lights)
    preexisting = {tool._guid_text(item.get_editor_property("attachment_guid"))
                   for cue in cues for item in tool._pair_attachments(cue)}
    originals = {t["show_index"]: tool._pair_attachments(cues[t["show_index"]]) for t in plan["targets"]}
    original_enabled = {tool._guid_text(a.get_editor_property("attachment_guid")):
                        bool(a.get_editor_property("enabled"))
                        for attachments in originals.values() for a in attachments if tool._is_light(a)}
    try:
        tool._set_pair_attachments(show, scratch_index,
                                   scratch_original + [tool._make_blank_light() for _ in range(padding)])
        fresh = list(show.get_editor_property("cues"))
        changed = show.replicate_light_attachments(
            fresh[scratch_index].get_editor_property("cue_guid"),
            [fresh[t["show_index"]].get_editor_property("cue_guid") for t in plan["targets"]])
        require(int(changed) == len(plan["targets"]),
                "REPLICATION_TARGET_COUNT|expected=%d|actual=%s" % (len(plan["targets"]), changed))
        tool._set_pair_attachments(show, scratch_index, scratch_original)
        tool._require_attachment_rows_equal(
            tool._attachment_rows(tool._pair_attachments(list(show.get_editor_property("cues"))[scratch_index])),
            scratch_before, "SCRATCH_NOT_RESTORED_EXACTLY")
        added_all = set()
        for target in plan["targets"]:
            index, replicated = _current_target(tool, show, target)
            vessels = [item for item in replicated if tool._is_light(item)]
            start, stop = target["existing_lights"], target["existing_lights"] + target["fixture_count"]
            require(len(vessels) >= stop, "MINTED_SLOT_COUNT|cue=%s|need=%d|actual=%d"
                    % (target["cue_label"], stop, len(vessels)))
            keep = set(target["retained_guids"])
            modified = []
            for attachment in originals[index]:
                guid = tool._guid_text(attachment.get_editor_property("attachment_guid"))
                if tool._is_light(attachment) and guid not in keep:
                    attachment.set_editor_property("enabled", False)
                modified.append(attachment)
            authored = []
            for vessel, fixture in zip(vessels[start:stop], target["fixtures"]):
                minted = tool._guid_text(vessel.get_editor_property("attachment_guid"))
                require(minted not in preexisting and minted not in added_all,
                        "MINTED_GUID_NOT_FRESH|guid=" + minted)
                authored.append(tool._overwrite_vessel(vessel, _template(tool, fixture, materials, meshes)))
                added_all.add(minted)
            tool._set_pair_attachments(show, index, modified + authored)
            target["added"] = [{"guid": tool._guid_text(a.get_editor_property("attachment_guid")),
                                "label": str(a.get_editor_property("label"))} for a in authored]
            require([a["label"] for a in target["added"]] == [f["label"] for f in target["fixtures"]],
                    "NEW_LABEL_ORDER_WRONG|cue=" + target["cue_label"])
            target["after_rows"] = tool._attachment_rows(modified + authored)
            target["after_hash"] = tool._rows_hash(target["after_rows"])
        require(len(added_all) == plan["fixture_count"], "ADDED_GUID_COUNT|expected=%d|actual=%d"
                % (plan["fixture_count"], len(added_all)))
    except Exception:
        tool._set_pair_attachments(show, scratch_index, scratch_original)
        for index, attachments in originals.items():
            for attachment in attachments:
                if tool._is_light(attachment):
                    attachment.set_editor_property("enabled", original_enabled[tool._guid_text(
                        attachment.get_editor_property("attachment_guid"))])
            tool._set_pair_attachments(show, index, attachments)
        tool._require_attachment_rows_equal(
            tool._attachment_rows(tool._pair_attachments(list(show.get_editor_property("cues"))[scratch_index])),
            scratch_before, "APPLY_ROLLBACK_SCRATCH_FAILED")
        for target in plan["targets"]:
            unused, attachments = _current_target(tool, show, target)
            tool._require_attachment_rows_equal(tool._attachment_rows(attachments), target["before_rows"],
                                                "APPLY_ROLLBACK_TARGET_FAILED|cue=" + target["cue_label"])
        raise


def _close(a, b):
    return abs(float(a) - float(b)) <= 1.0e-3 * max(1.0, abs(float(b)))


def _verify_fixture_values(plan, rows_by_guid):
    """Setter-lie guard: every authored value, read back from the Show, against
    the PLAN (not against rows captured from the same in-memory objects)."""
    for target in plan["targets"]:
        by_label = {row["label"]: row for row in rows_by_guid[target["cue_guid"]]}
        for fixture in target["fixtures"]:
            row = by_label.get(fixture["label"])
            require(row is not None, "FIXTURE_ROW_MISSING|label=" + fixture["label"])
            require(row["enabled"], "FIXTURE_DISABLED|label=" + fixture["label"])
            if fixture["authored_kind"] != "LIGHT":
                continue
            lighting, drama, keying = row["lighting"], row["lighting"]["drama"], fixture["distance_keying"]
            require(_close(lighting["intensity"], fixture["intensity"]), "INTENSITY_READBACK|" + fixture["label"])
            require(bool(lighting["cast_shadows"]) == bool(fixture["cast_shadows"]),
                    "CAST_SHADOWS_READBACK|" + fixture["label"])
            require(bool(drama["strike_on_approach"]), "STRIKE_FLAG_READBACK|" + fixture["label"])
            require(_close(drama["strike_distance_cm"], keying["strike_distance_cm"]),
                    "STRIKE_DISTANCE_READBACK|" + fixture["label"])
            require(_close(drama["strike_ramp_cm"], keying["ramp_distance_cm"]), "RAMP_READBACK|" + fixture["label"])
            require(_close(drama["ignition_stutter"], keying.get("ignition_stutter", 0.0)),
                    "STUTTER_READBACK|" + fixture["label"])
            require(str(keying["after_pass"]).upper() in str(drama["after_pass"]).upper(),
                    "AFTER_PASS_READBACK|" + fixture["label"])
            for key, value in sorted(fixture.get("drama", {}).items()):  # 6 Oct: per-lamp slow move
                got = drama[key]
                require(bool(got) == value if isinstance(value, bool) else _close(got, value),
                        "SLOW_MOVE_READBACK|%s|%s" % (key, fixture["label"]))


def _verify_applied(tool, show, plan, outside_before):
    all_rows = tool._all_pair_rows(show)
    require(tool._outside_hash(all_rows, plan["target_cue_guids"]) == outside_before,
            "OUTSIDE_TARGET_SCOPE_CHANGED")
    read_rows = {}
    for target in plan["targets"]:
        unused, attachments = _current_target(tool, show, target)
        rows = tool._attachment_rows(attachments)
        read_rows[target["cue_guid"]] = rows
        tool._require_attachment_rows_equal(rows, target["after_rows"], "APPLY_READBACK_MISMATCH|cue=" + target["cue_label"])
        keep = set(target["retained_guids"])
        before = {row["guid"]: row for row in target["before_rows"]}
        count = len(target["before_rows"])
        for attachment, row in zip(attachments[:count], rows[:count]):
            if row["guid"] in keep:
                require(_canonical(row) == _canonical(before[row["guid"]]), "RETAINED_LIGHT_CHANGED|" + row["label"])
            elif tool._is_light(attachment):
                require(not row["enabled"], "EXISTING_LIGHT_STILL_ENABLED|" + row["label"])
    _verify_fixture_values(plan, read_rows)
    plain, unused = _runtime_plain(tool, show)
    after = passage_casters(tool, plain, plan["bay_guids"])
    require(after == plan["shadow"]["passage_after"], "SHADOW_READBACK_MISMATCH|expected=%d|actual=%d"
            % (plan["shadow"]["passage_after"], after))
    return after


def _materialize_passage(show, actor_prefix):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = [actor for actor in subsystem.get_all_level_actors()
                if actor.get_class().get_name() == "InfinityStagePassageActor"
                and actor.get_actor_label().startswith(actor_prefix)
                and actor.get_editor_property("show_asset") == show]
    require(len(passages) == 1, "PASSAGE_ACTOR_COUNT|prefix=%s|count=%d" % (actor_prefix, len(passages)))
    passage = passages[0]
    require(bool(passage.materialize_passage()), "PASSAGE_MATERIALIZE_FAILED|" + actor_prefix)
    structures = [actor for actor in subsystem.get_all_level_actors()
                  if actor.get_class().get_name() == "InfinityStageStructureActor"
                  and actor.get_editor_property("passage") == passage]
    require(len(structures) <= 1, "STRUCTURE_COUNT|count=%d" % len(structures))
    result = {"passage": passage.get_actor_label(), "structure": None}
    if structures:
        require(bool(structures[0].materialize_structure()), "STRUCTURE_REFIT_FAILED")
        result["structure"] = structures[0].get_actor_label()
    return result


def _count_passage_actors(show, actor_prefix):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return sum(1 for actor in subsystem.get_all_level_actors()
               if actor.get_class().get_name() == "InfinityStagePassageActor"
               and actor.get_actor_label().startswith(actor_prefix)
               and actor.get_editor_property("show_asset") == show)


def _other_score_targets(passage_key):
    guids = set()
    for path in glob.glob(os.path.join(HERE, "lighting_scores_record_P0?.json")):
        if path == _record_path(passage_key):
            continue
        with open(path, encoding="utf-8") as handle:
            guids.update(json.load(handle).get("plan", {}).get("target_cue_guids", []))
    return guids


def _run(mode, passage_key, ack_records, prototype_absent):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": mode, "passage": passage_key, "run": run,
              "tests_required": list(TESTS_REQUIRED)}
    record_path, report_path = _record_path(passage_key), _report_path(passage_key)
    tool = None
    try:
        tool = load_p04_tool()
        report["p04_tool_sha256"] = tool.SCORES_SOURCE_SHA256
        scores = load_scores()
        report["scores_sha256"] = _sha256_path(SCORES_PATH)
        base_looks, base_info = load_base_looks(scores)
        report["base_looks"] = base_info
        looks = resolve_looks(scores, base_looks)
        passage_cfg = scores["passages"][passage_key]
        world = tool._require_context()
        materials, meshes, flicker_declared, flicker_state = _assets(tool, looks, scores)
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        p04_record = None
        if passage_cfg.get("prototype"):
            proto_path = os.path.join(HERE, passage_cfg["prototype"]["record"])
            if os.path.isfile(proto_path):
                with open(proto_path, encoding="utf-8") as handle:
                    p04_record = json.load(handle)

        if mode in ("DRY", "APPLY"):
            require(not os.path.exists(record_path), "ACTIVE_REVERT_RECORD_EXISTS|" + record_path)
            plain, passages = _runtime_plain(tool, show)
            plan = build_score_plan(tool, scores, looks, passage_key, passages, plain,
                                    p04_record, prototype_absent)
            _require_show_resolution(tool, show, plan)
            _apply_live_aims(tool, show, plan)
            require_no_cross_live(plan)
            timing = _passage_timing(tool, show, plan)
            plan["timing_readout"] = timing
            beat_map = passage_cfg.get("beat_map", {}).get("beats", [])
            plan["beat_check"] = beat_check(beat_map, timing["rows"]) if (beat_map and timing["ok"]) else None
            cues = list(show.get_editor_property("cues"))
            for target in plan["targets"]:
                target["before_rows"] = tool._attachment_rows(tool._pair_attachments(cues[target["show_index"]]))
                target["before_hash"] = tool._rows_hash(target["before_rows"])
            foreign = scan_foreign_records(
                [os.path.join(os.path.dirname(HERE), name) for name in os.listdir(os.path.dirname(HERE))
                 if name.startswith("Codex")],
                plan["target_cue_guids"],
                exclude=[record_path] + ([os.path.join(HERE, passage_cfg["prototype"]["record"])]
                                         if passage_cfg.get("prototype") else []))
            plan["foreign_records"] = foreign
            unacknowledged = sorted({hit["path"] for hit in foreign} - set(ack_records or []))
            actors = _count_passage_actors(show, passage_cfg["passage_actor_label_prefix"])
            require(actors == 1, "PASSAGE_ACTOR_COUNT|prefix=%s|count=%d"
                    % (passage_cfg["passage_actor_label_prefix"], actors))
            plan["body_assets"] = body_asset_plan([f for t in plan["targets"] for f in t["fixtures"]])
            used_flicker = {f["flicker"]["material"] for t in plan["targets"] for f in t["fixtures"]
                            if f.get("authored_kind") == "LIGHT" and f["flicker"]["material"]}
            plan["flicker_instances"] = {p: flicker_declared[p] for p in sorted(used_flicker) if p in flicker_declared}
            body_api = UnrealBodyAssets()
            body_state = {path: ("REUSE" if body_api.exists(path) else "CREATE")
                          for kind in ("mis", "meshes") for path in plan["body_assets"][kind]}
            for parent in {spec["parent"] for spec in plan["body_assets"]["mis"].values()}:
                require(body_api.exists(parent), "BODY_PARENT_MISSING|" + parent)
            # DRY: a body mesh that does not exist yet is template-checked with its source mesh.
            template_meshes = dict(meshes)
            for path, spec in plan["body_assets"]["meshes"].items():
                template_meshes[path] = (unreal.load_asset(path) if body_state[path] == "REUSE"
                                         else meshes[spec["source"]])
            templates = sum(1 for t in plan["targets"] for f in t["fixtures"]
                            if _template(tool, f, materials, template_meshes) is not None)
            require(templates == plan["fixture_count"], "TEMPLATE_BUILD_COUNT")
            report.update({"plan_summary": {
                "bays": plan["bay_count"], "targets": len(plan["targets"]), "skipped": plan["skipped"],
                "retained": plan["retained"], "fixtures": plan["fixture_count"],
                "lights": plan["light_fixture_count"], "practical_props": plan["practical_prop_count"],
                "disabled": plan["existing_lights_disabled"], "shadow": plan["shadow"],
                "prototype": plan["prototype"], "yield_to_events": plan["yield_to_events"],
                "foreign_records": foreign,
                "unacknowledged_foreign_records": unacknowledged, "templates_built": templates,
                "body_assets": body_state,
                "flicker_instances": {p: flicker_state[p] for p in plan["flicker_instances"]},
                "warnings": plan["warnings"],
                "beat_check": plan["beat_check"],
                "no_cross_live": None if not plan.get("no_cross") else
                {"spots": len(plan["no_cross"]["live"]), "verdict": "PASS"}}})
            if mode == "DRY":
                report.update({"ok": True, "mutated": False, "plan": plan, "census": tool._dirty_census()})
                tool._write_json(report_path, report)
                unreal.log("LIGHTING_SCORES_DRY_OK|run=%s|passage=%s|targets=%d|skipped=%d|attachments=%d|lights=%d|"
                           "practical_props=%d|disabled=%d|retained=%d|shadow=%d->%d|foreign=%d|no_cross=%s|mutated=0"
                           % (run, passage_key, len(plan["targets"]), len(plan["skipped"]), plan["fixture_count"],
                              plan["light_fixture_count"], plan["practical_prop_count"],
                              plan["existing_lights_disabled"], len(plan["retained"]),
                              plan["shadow"]["passage_before"], plan["shadow"]["passage_after"], len(foreign),
                              "OFF" if not plan.get("no_cross") else "PASS_%d_SPOTS" % len(plan["no_cross"]["live"])))
                return report
            require(not unacknowledged, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacknowledged))
            outside_before = tool._outside_hash(tool._all_pair_rows(show), plan["target_cue_guids"])
            backup = tool._backup("PreLightingScores%s-" % passage_key, run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": passage_key,
                      "scores_sha256": report["scores_sha256"], "base_looks": base_info,
                      "p04_tool_sha256": report["p04_tool_sha256"], "backup": backup,
                      "outside_before_hash": outside_before, "plan": plan}
            tool._write_json(record_path, record, exclusive=True)
            if plan["body_assets"]["mis"] or plan["body_assets"]["meshes"]:
                # Created and saved BEFORE the Show mutation, so _save_narrow still sees only Show + level dirty.
                try:
                    record["body_assets_created"] = ensure_body_assets(body_api, plan["body_assets"])
                finally:
                    tool._write_json(record_path, record)
                require(tool._dirty_census() == {"content": [], "maps": []},
                        "DIRTY_AFTER_BODY_ASSETS|" + _canonical(tool._dirty_census()))
                for path in plan["body_assets"]["meshes"]:
                    meshes[path] = unreal.load_asset(path)
            if plan["flicker_instances"]:
                try:
                    record["flicker_instances_created"] = ensure_flicker_instances(
                        UnrealFlickerInstances(), plan["flicker_instances"])
                finally:
                    tool._write_json(record_path, record)
                require(tool._dirty_census() == {"content": [], "maps": []},
                        "DIRTY_AFTER_FLICKER_INSTANCES|" + _canonical(tool._dirty_census()))
                for path in plan["flicker_instances"]:
                    materials[path] = unreal.load_asset(path)
            try:
                _mutate_apply(tool, show, plan, materials, meshes, _other_score_targets(passage_key))
            except Exception:
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(record_path, record)
                os.rename(record_path, record_path + ".failed-" + run)
                raise
            record.update({"status": "mutated_verified", "plan": plan})
            tool._write_json(record_path, record)
            _verify_applied(tool, show, plan, outside_before)
            materialized = _materialize_passage(show, passage_cfg["passage_actor_label_prefix"])
            tool._save_narrow()
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            after = _verify_applied(tool, readback, plan, outside_before)
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "saved_census": tool._dirty_census()})
            tool._write_json(record_path, record)
            tool._queue_master_test(world, "LIGHTING_SCORES", run)
            report.update({"ok": True, "backup": backup, "record": record_path, "materialized": materialized,
                           "shadow_readback": after, "saved_master_test": "queued", "census": tool._dirty_census()})
            tool._write_json(report_path, report)
            unreal.log("LIGHTING_SCORES_APPLY_OK|run=%s|passage=%s|targets=%d|attachments=%d|disabled=%d|shadow=%d->%d|"
                       "show_saved=1|level_saved=1|readback=1|saved_master=queued|scene_cut=RUN_SEPARATELY"
                       % (run, passage_key, len(plan["targets"]), plan["fixture_count"],
                          plan["existing_lights_disabled"], plan["shadow"]["passage_before"], after))
            return report

        require(os.path.isfile(record_path), "REVERT_RECORD_ABSENT|" + record_path)
        record = tool._read_json(record_path)
        require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|" + str(record.get("status")))
        require(record.get("passage") == passage_key, "REVERT_RECORD_PASSAGE")
        plan = record["plan"]
        plain, unused = _runtime_plain(tool, show)
        before_revert = passage_casters(tool, plain, plan["bay_guids"])
        backup = tool._backup("PreLightingScores%sRevert-" % passage_key, run)
        _mutate_revert(tool, show, plan)
        plain, unused = _runtime_plain(tool, show)
        after_revert = passage_casters(tool, plain, plan["bay_guids"])
        expected = before_revert - plan["shadow"]["target_after"] + plan["shadow"]["target_before"]
        require(after_revert == expected, "REVERT_SHADOW_MISMATCH|expected=%d|actual=%d" % (expected, after_revert))
        materialized = _materialize_passage(show, passage_cfg["passage_actor_label_prefix"])
        tool._save_narrow()
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        for target in plan["targets"]:
            unused_index, attachments = _current_target(tool, readback, target)
            tool._require_attachment_rows_equal(tool._attachment_rows(attachments), target["before_rows"],
                                                "REVERT_READBACK_NOT_EXACT|cue=" + target["cue_label"])
        body_revert = None
        if record.get("body_assets_created"):
            plain, unused = _runtime_plain(tool, readback)
            referenced = {str(att.get("mesh", "")).split(".")[0] for cue in plain for att in cue["attachments"]}
            body_revert = revert_body_assets(UnrealBodyAssets(), record["body_assets_created"], referenced)
            require(tool._dirty_census() == {"content": [], "maps": []},
                    "DIRTY_AFTER_BODY_REVERT|" + _canonical(tool._dirty_census()))
        report["body_assets_revert"] = body_revert
        # Flicker instances are shared, tiny and parameter-only: REVERT keeps them (never deletes).
        report["flicker_instances_kept"] = record.get("flicker_instances_created", [])
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        tool._queue_master_test(world, "LIGHTING_SCORES_REVERT", run)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized,
                       "shadow": {"before_revert": before_revert, "after_revert": after_revert},
                       "saved_master_test": "queued", "census": tool._dirty_census()})
        tool._write_json(report_path, report)
        unreal.log("LIGHTING_SCORES_REVERT_OK|run=%s|passage=%s|targets=%d|shadow=%d->%d|show_saved=1|level_saved=1|"
                   "readback=1|saved_master=queued|scene_cut=RUN_SEPARATELY"
                   % (run, passage_key, len(plan["targets"]), before_revert, after_revert))
        return report
    except Exception as error:  # noqa: BLE001 - preserve a report for every stop.
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None and unreal is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        if unreal is not None:
            unreal.log_error("LIGHTING_SCORES_STOPPED|run=%s|mode=%s|passage=%s|%s"
                             % (run, mode, passage_key, report["error"]))
        raise


def _mutate_revert(tool, show, plan):
    outside_before = tool._outside_hash(tool._all_pair_rows(show), plan["target_cue_guids"])
    current = {}
    current_enabled = {}
    try:
        for target in plan["targets"]:
            index, attachments = _current_target(tool, show, target)
            current[index] = attachments
            for a in attachments:
                if tool._is_light(a):
                    current_enabled[tool._guid_text(a.get_editor_property("attachment_guid"))] = bool(
                        a.get_editor_property("enabled"))
            tool._require_attachment_rows_equal(tool._attachment_rows(attachments), target["after_rows"],
                                                "REVERT_CURRENT_STATE_DRIFT|cue=" + target["cue_label"])
            added = {row["guid"] for row in target["added"]}
            before_enabled = {row["guid"]: row["enabled"] for row in target["before_rows"]}
            restored, removed = [], 0
            for a in attachments:
                guid = tool._guid_text(a.get_editor_property("attachment_guid"))
                if guid in added:
                    removed += 1
                    continue
                require(guid in before_enabled, "REVERT_UNKNOWN_ATTACHMENT|cue=%s|guid=%s" % (target["cue_label"], guid))
                if tool._is_light(a):
                    a.set_editor_property("enabled", bool(before_enabled[guid]))
                restored.append(a)
            require(removed == len(added), "REVERT_REMOVE_COUNT|cue=" + target["cue_label"])
            tool._set_pair_attachments(show, index, restored)
            tool._require_attachment_rows_equal(tool._attachment_rows(restored), target["before_rows"],
                                                "REVERT_NOT_EXACT|cue=" + target["cue_label"])
        require(tool._outside_hash(tool._all_pair_rows(show), plan["target_cue_guids"]) == outside_before,
                "REVERT_OUTSIDE_TARGET_SCOPE_CHANGED")
    except Exception:
        for index, attachments in current.items():
            for a in attachments:
                if tool._is_light(a):
                    a.set_editor_property("enabled", current_enabled[tool._guid_text(
                        a.get_editor_property("attachment_guid"))])
            tool._set_pair_attachments(show, index, attachments)
        raise


def main(mode=None, passage=None):
    selected = str(mode or globals().get("LIGHTING_SCORES_MODE", "DRY")).upper()
    require(selected in VALID_MODES, "MODE_INVALID|mode=" + selected)
    passage_key = str(passage or globals().get("LIGHTING_SCORES_PASSAGE", "")).upper()
    require(PASSAGE_KEY.match(passage_key), "PASSAGE_REQUIRED|set LIGHTING_SCORES_PASSAGE to P01..P06")
    require(unreal is not None, "UNREAL_REQUIRED_FOR_MODE|mode=" + selected)
    return _run(selected, passage_key, list(globals().get("LIGHTING_SCORES_ACK_RECORDS", []) or []),
                globals().get("LIGHTING_SCORES_PROTOTYPE_ABSENT"))


if unreal is not None:
    main()
