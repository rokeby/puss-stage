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
VALID_ROLES = ("TOP", "LOW_SIDE", "BEAM", "PRACTICAL")
ROLE_MAX = {"TOP": 2, "LOW_SIDE": 2, "BEAM": 1, "PRACTICAL": 2}
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
}
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
    require(not row["cast_shadows"] or role == "LOW_SIDE", "NON_SIDE_SHADOW_CASTER|" + where)
    flicker = row.get("flicker", {})
    require("mode" in flicker and "material" in flicker, "FLICKER_UNDECLARED|" + where)
    require(flicker["material"] is None or str(flicker["material"]).startswith(FLICKER_ROOT),
            "FLICKER_MATERIAL_UNKNOWN|" + where)
    if role == "TOP":
        require(row["slot"].rsplit("_", 1)[-1] in ("L", "R"), "TOP_SLOT_SIDE_UNKNOWN|" + where)
    if "aim_wing_side" in row or "aim_offset_pair_cm" in row:
        require(row["type"] == "SPOT" and row.get("aim_wing_side") in ("LEFT", "RIGHT"),
                "WING_AIM_BAD|" + where)
        offset = row.get("aim_offset_pair_cm")
        require(isinstance(offset, list) and len(offset) == 3
                and all(math.isfinite(float(v)) for v in offset), "WING_AIM_OFFSET_BAD|" + where)
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
    _mirror_explicit_aims(fixtures, spec)
    for row in fixtures:
        if row["authored_kind"] == "LIGHT":
            validate_instrument(row, "%s|look=%s|slot=%s" % (where, look_name, row["slot"]))
    return fixtures


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


def no_cross_config(passage):
    """None when the passage does not enable the rule; else the merged settings."""
    raw = passage.get("no_cross_shots")
    if raw in (None, False):
        return None
    cfg = dict(NO_CROSS_DEFAULTS)
    if raw is not True:
        require(isinstance(raw, dict) and raw.get("enabled", True) is True
                and set(raw).issubset(set(NO_CROSS_DEFAULTS) | {"enabled", "note"}),
                "BAD_NO_CROSS_CONFIG|" + _canonical(raw))
        cfg.update({k: float(v) for k, v in raw.items() if k in NO_CROSS_DEFAULTS})
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


def bay_output(fixtures):
    out = {unit: 0.0 for unit in UNITS}
    for row in fixtures:
        if row.get("authored_kind") == "LIGHT":
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


def _assets(tool, looks):
    config = {"looks": looks}
    return tool._materials(config), tool._practical_meshes(config)


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
        materials, meshes = _assets(tool, looks)
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
            templates = sum(1 for t in plan["targets"] for f in t["fixtures"]
                            if _template(tool, f, materials, meshes) is not None)
            require(templates == plan["fixture_count"], "TEMPLATE_BUILD_COUNT")
            report.update({"plan_summary": {
                "bays": plan["bay_count"], "targets": len(plan["targets"]), "skipped": plan["skipped"],
                "retained": plan["retained"], "fixtures": plan["fixture_count"],
                "lights": plan["light_fixture_count"], "practical_props": plan["practical_prop_count"],
                "disabled": plan["existing_lights_disabled"], "shadow": plan["shadow"],
                "prototype": plan["prototype"], "yield_to_events": plan["yield_to_events"],
                "foreign_records": foreign,
                "unacknowledged_foreign_records": unacknowledged, "templates_built": templates,
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
