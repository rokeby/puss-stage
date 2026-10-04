"""Guarded P04 lighting-look prototype authoring tool.

Modes are DRY (default), APPLY, and REVERT. Set ``LIGHTING_LOOKS_MODE`` through
``runpy.run_path(..., init_globals={...})`` when executing in Unreal.

The intensity ramp uses the project's existing distance route, not Sequencer:

* ``FInfinityStageLightDrama`` declares strike-on-approach as camera-distance
  driven (InfinityStageLightDrama.h:20-31).
* ``EvaluateStrike`` maps the last ``StrikeRampCm`` to intensity
  (InfinityStageLightDrama.cpp:24-59).
* ``AInfinityStagePassageActor`` evaluates it against the camera and lamp route
  distances in game worlds (InfinityStagePassageActor.cpp:1620-1660).

No source or Plugin file is modified. APPLY and REVERT back up the Show and
level, materialize Passage 04 only, save only those two packages, read the Show
back, require a clean census, and queue only SavedMasterMatchesShow.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness import.
    unreal = None


def _load_attachment_state():
    try:
        import _infinity_attachment_state as module
        return module
    except ModuleNotFoundError:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_infinity_attachment_state.py")
        spec = importlib.util.spec_from_file_location("_infinity_attachment_state", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


S = _load_attachment_state()


EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
PASSAGE_NUMBER = 4
VALID_MODES = ("DRY", "APPLY", "REVERT")
VALID_ROLES = ("TOP", "LOW_SIDE", "BEAM", "PRACTICAL")
ROLE_LIMITS = {"TOP": (2, 2), "LOW_SIDE": (2, 2), "BEAM": (0, 1), "PRACTICAL": (0, 2)}
REQUIRED_LOOKS = {"MOODY", "INDUSTRIAL", "THEATRICAL", "SPOT", "WASH"}
LIGHT_FIELDS = S.LIGHT_FIELDS
LIGHT_OBJECT_FIELDS = S.LIGHT_OBJECT_FIELDS
DRAMA_FIELDS = S.DRAMA_FIELDS
EFFECT_FIELDS = S.EFFECT_FIELDS
EFFECT_GUID_FIELDS = S.EFFECT_GUID_FIELDS
EFFECT_OBJECT_FIELDS = S.EFFECT_OBJECT_FIELDS
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lighting_looks.json")
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lighting_looks_report.json")
RECORD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lighting_looks_revert_record.json")
# Gary 4 Oct ("go the quick route"): W&T placed the P04 fence (FB run FV3FB-20261004-01) on the
# tune 3d target cues before this revert. REVERT leaves exactly those fence props in place and
# excludes them from its exactness checks. Only PROP (non-light) attachments named in a PASS
# verify record qualify, and none may collide with this record's own GUIDs.
FOREIGN_PROP_RECORDS = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "CodexFlatV3", "fence", "fb_verify_FV3FB-20261004-01.json")]


def _foreign_prop_guids(record=None):
    guids = set()
    for path in FOREIGN_PROP_RECORDS:
        require(os.path.isfile(path), "FOREIGN_RECORD_MISSING|path=" + path)
        with open(path, encoding="utf-8") as handle:
            foreign_record = json.load(handle)
        require(foreign_record.get("status") == "PASS", "FOREIGN_RECORD_STATUS|path=" + path)
        for name, row in foreign_record.get("found", {}).items():
            require("PROP" in str(row.get("kind")), "FOREIGN_NOT_PROP|" + name)
            guids.add(str(row["guid"]).upper())
    if record is not None:
        own = set()
        for target in record["plan"]["targets"]:
            own |= {str(row["guid"]).upper() for row in target["added"]}
            own |= {str(row["guid"]).upper() for row in target["before_rows"]}
        require(not (own & guids), "FOREIGN_GUID_COLLISION|count=%d" % len(own & guids))
    return guids


class LightingLooksError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise LightingLooksError(str(message))


def _finite(value, label):
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|value=%r" % (label, value))
    return number


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _state_hash(value):
    return _sha256_bytes(_canonical(value).encode("utf-8"))


def load_config(path=CONFIG_PATH):
    data = _read_json(path)
    validate_config(data)
    return data


def validate_config(data):
    require(data.get("schema_version") == 1, "CONFIG_SCHEMA_NOT_1")
    require(data.get("existing_light_policy") == "disable_all_in_target_bay",
            "EXISTING_LIGHT_POLICY_UNSAFE")
    keying = data.get("distance_keying", {})
    require(keying.get("mechanism") == "FInfinityStageLightDrama strike-on-approach",
            "DISTANCE_MECHANISM_WRONG")
    require(abs(_finite(keying.get("ramp_distance_cm"), "RAMP_DISTANCE") - 150.0) < 1.0e-9,
            "RAMP_NOT_150_CM")
    require(abs(_finite(keying.get("strike_distance_cm"), "STRIKE_DISTANCE") - 650.0) < 1.0e-9,
            "STRIKE_NOT_650_CM")
    require(keying.get("after_pass") == "HOLD", "AFTER_PASS_NOT_HOLD")
    require(data.get("shadow_budget", {}).get("rule") == "after_lte_before",
            "SHADOW_BUDGET_RULE_WRONG")
    cap = data.get("shadow_budget", {}).get("cap")
    require(isinstance(cap, int) and cap > 0, "SHADOW_CAP_UNDECLARED")
    _hex_guid(data.get("p04_scope", {}).get("passage_first_cue_guid"), "P04_SCOPE_FIRST_CUE")

    looks = data.get("looks", {})
    require(set(looks) == REQUIRED_LOOKS,
            "LOOK_SET_WRONG|actual=%s" % ",".join(sorted(looks)))
    all_slots = {}
    for look_name, look in sorted(looks.items()):
        instruments = look.get("instruments", [])
        require(instruments, "LOOK_EMPTY|look=" + look_name)
        slots = [row.get("slot") for row in instruments]
        require(len(slots) == len(set(slots)), "DUPLICATE_SLOT|look=" + look_name)
        counts = {role: 0 for role in VALID_ROLES}
        for row in instruments:
            role = row.get("role")
            require(role in VALID_ROLES, "BAD_ROLE|look=%s|role=%s" % (look_name, role))
            counts[role] += 1
            require(row.get("type") in ("SPOT", "POINT", "RECT"),
                    "BAD_LIGHT_TYPE|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(row.get("intensity_units") in ("CANDELAS", "LUMENS"),
                    "BAD_UNITS|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(_finite(row.get("intensity"), "INTENSITY") >= 0.0,
                    "NEGATIVE_INTENSITY|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(_finite(row.get("attenuation_cm"), "ATTENUATION") > 0.0,
                    "BAD_ATTENUATION|look=%s|slot=%s" % (look_name, row.get("slot")))
            rgb = row.get("color_rgb_linear", [])
            require(len(rgb) == 3 and all(_finite(v, "RGB") >= 0.0 for v in rgb),
                    "BAD_RGB|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(1000.0 <= _finite(row.get("temperature_kelvin"), "TEMPERATURE") <= 15000.0,
                    "BAD_TEMPERATURE|look=%s|slot=%s" % (look_name, row.get("slot")))
            transform = row.get("transform", {})
            require(len(transform.get("location_cm", [])) == 3
                    and len(transform.get("rotation_rpy_deg", [])) == 3,
                    "BAD_TRANSFORM|look=%s|slot=%s" % (look_name, row.get("slot")))
            if row.get("type") == "SPOT":
                inner = _finite(row.get("inner_cone_deg"), "INNER_CONE")
                outer = _finite(row.get("outer_cone_deg"), "OUTER_CONE")
                require(0.0 <= inner <= outer <= 89.0,
                        "BAD_CONE|look=%s|slot=%s" % (look_name, row.get("slot")))
            require(not row.get("cast_shadows") or role == "LOW_SIDE",
                    "NON_SIDE_SHADOW_CASTER|look=%s|slot=%s" % (look_name, row.get("slot")))
            flicker = row.get("flicker", {})
            require("mode" in flicker and "material" in flicker,
                    "FLICKER_UNDECLARED|look=%s|slot=%s" % (look_name, row.get("slot")))
        for role, (minimum, maximum) in ROLE_LIMITS.items():
            require(minimum <= counts[role] <= maximum,
                    "ROLE_COUNT|look=%s|role=%s|count=%d" % (look_name, role, counts[role]))
        practicals = [row for row in instruments if row["role"] == "PRACTICAL"]
        require(len(practicals) == 2,
                "PRACTICAL_COUNT_NOT_2|look=%s|count=%d" % (look_name, len(practicals)))
        require(sum(float(row["intensity"]) == 0.0 for row in practicals) == 1,
                "PRACTICAL_DEAD_COUNT_NOT_1|look=" + look_name)
        for practical in practicals:
            visible = practical.get("visible_mesh", {})
            require(str(visible.get("mesh", "")).startswith(("/Game/", "/Engine/")),
                    "PRACTICAL_MESH_MISSING|look=%s|slot=%s" %
                    (look_name, practical["slot"]))
            require(bool(visible.get("style")),
                    "PRACTICAL_STYLE_MISSING|look=%s|slot=%s" %
                    (look_name, practical["slot"]))
            require(isinstance(visible.get("emissive"), bool),
                    "PRACTICAL_EMISSIVE_UNDECLARED|look=%s|slot=%s" %
                    (look_name, practical["slot"]))
            require(len(visible.get("rotation_rpy_deg", [])) == 3
                    and len(visible.get("scale", [])) == 3
                    and all(_finite(value, "PRACTICAL_SCALE") > 0.0
                            for value in visible.get("scale", [])),
                    "PRACTICAL_MESH_TRANSFORM_BAD|look=%s|slot=%s" %
                    (look_name, practical["slot"]))
        require(sum(1 for row in instruments if row.get("cast_shadows")) == 2,
                "LOOK_SHADOW_CASTERS_NOT_2|look=" + look_name)
        all_slots[look_name] = slots

    _require_unique_bay_guids(data)
    if "tune4" in data:
        validate_tune4(data["tune4"])

    for look_name, expected_ratio in (("MOODY", 16.0), ("THEATRICAL", 4.0)):
        sides = [float(row["intensity"]) for row in looks[look_name]["instruments"]
                 if row["role"] == "LOW_SIDE"]
        actual = max(sides) / min(sides)
        require(abs(actual - expected_ratio) < 1.0e-9,
                "KEY_FILL_RATIO|look=%s|actual=%s" % (look_name, actual))
        require(abs(float(looks[look_name]["key_fill_ratio"]) - expected_ratio) < 1.0e-9,
                "KEY_FILL_METADATA|look=" + look_name)

    bays = data.get("bay_plan", [])
    require([row.get("bay_index") for row in bays] == list(range(1, 7)),
            "BAY_PLAN_NOT_1_TO_6")
    require([row.get("look") for row in bays]
            == ["MOODY", "MOODY", "INDUSTRIAL", "INDUSTRIAL", "THEATRICAL", "THEATRICAL"],
            "BAY_LOOK_ORDER_WRONG")
    for row in bays:
        expected = "P04 Wing %03d" % row["bay_index"]
        require(row.get("expected_label") == expected,
                "BAY_LABEL_WRONG|bay=%s" % row.get("bay_index"))
        require(row.get("resolve_identity") == "CueGuid; label is a post-resolve drift check only",
                "BAY_IDENTITY_NOT_GUID|bay=%s" % row.get("bay_index"))
        require("cue_guid" in row, "BAY_CUE_GUID_MISSING|bay=%s" % row.get("bay_index"))
        _hex_guid(row["cue_guid"], "BAY_CUE")
        require(_finite(row.get("level_scale"), "LEVEL_SCALE") > 0.0,
                "BAD_LEVEL_SCALE|bay=%s" % row.get("bay_index"))
        require(row["look"] in all_slots, "UNKNOWN_BAY_LOOK|bay=%s" % row["bay_index"])
        mirror_roles = row.get("mirror_roles", [])
        require(isinstance(mirror_roles, list)
                and len(mirror_roles) == len(set(mirror_roles))
                and set(mirror_roles).issubset(VALID_ROLES),
                "BAD_MIRROR_ROLES|bay=%s" % row["bay_index"])
        overrides = row.get("instrument_overrides", {})
        require(isinstance(overrides, dict)
                and set(overrides).issubset(set(all_slots[row["look"]])),
                "BAD_OVERRIDE_SLOTS|bay=%s" % row["bay_index"])
        allowed = {"intensity", "color_rgb_linear", "temperature_kelvin",
                   "volumetric_scattering", "inner_cone_deg", "outer_cone_deg",
                   "attenuation_cm", "location_cm", "aim_wing_side",
                   "aim_offset_pair_cm"}
        for slot, values in overrides.items():
            require(isinstance(values, dict) and set(values).issubset(allowed),
                    "BAD_OVERRIDE_FIELDS|bay=%s|slot=%s" % (row["bay_index"], slot))
            source = next(item for item in looks[row["look"]]["instruments"]
                          if item["slot"] == slot)
            if "intensity" in values:
                require(_finite(values["intensity"], "OVERRIDE_INTENSITY") >= 0.0,
                        "BAD_OVERRIDE_INTENSITY|bay=%s|slot=%s" % (row["bay_index"], slot))
            if "color_rgb_linear" in values:
                rgb = values["color_rgb_linear"]
                require(len(rgb) == 3 and all(_finite(v, "OVERRIDE_RGB") >= 0.0 for v in rgb),
                        "BAD_OVERRIDE_RGB|bay=%s|slot=%s" % (row["bay_index"], slot))
            if "temperature_kelvin" in values:
                temperature = _finite(values["temperature_kelvin"], "OVERRIDE_TEMPERATURE")
                require(1000.0 <= temperature <= 15000.0,
                        "BAD_OVERRIDE_TEMPERATURE|bay=%s|slot=%s" % (row["bay_index"], slot))
            if "volumetric_scattering" in values:
                require(_finite(values["volumetric_scattering"], "OVERRIDE_VOLUMETRIC") >= 0.0,
                        "BAD_OVERRIDE_VOLUMETRIC|bay=%s|slot=%s" % (row["bay_index"], slot))
            if "attenuation_cm" in values:
                require(_finite(values["attenuation_cm"], "OVERRIDE_ATTENUATION") > 0.0,
                        "BAD_OVERRIDE_ATTENUATION|bay=%s|slot=%s" %
                        (row["bay_index"], slot))
            if "location_cm" in values:
                location = values["location_cm"]
                require(isinstance(location, list) and len(location) == 3
                        and all(math.isfinite(float(value)) for value in location),
                        "OVERRIDE_LOCATION_BAD|bay=%s|slot=%s" %
                        (row["bay_index"], slot))
            if "inner_cone_deg" in values or "outer_cone_deg" in values:
                require(source["type"] == "SPOT",
                        "CONE_OVERRIDE_NOT_SPOT|bay=%s|slot=%s" %
                        (row["bay_index"], slot))
                inner = _finite(values.get("inner_cone_deg", source["inner_cone_deg"]),
                                "OVERRIDE_INNER_CONE")
                outer = _finite(values.get("outer_cone_deg", source["outer_cone_deg"]),
                                "OVERRIDE_OUTER_CONE")
                require(0.0 <= inner <= outer <= 89.0,
                        "BAD_OVERRIDE_CONE|bay=%s|slot=%s" % (row["bay_index"], slot))
            if "aim_wing_side" in values or "aim_offset_pair_cm" in values:
                require(source["type"] == "SPOT",
                        "WING_AIM_NOT_SPOT|bay=%s|slot=%s" %
                        (row["bay_index"], slot))
                require(values.get("aim_wing_side") in ("LEFT", "RIGHT"),
                        "WING_AIM_SIDE_BAD|bay=%s|slot=%s" %
                        (row["bay_index"], slot))
                offset = values.get("aim_offset_pair_cm")
                require(isinstance(offset, list) and len(offset) == 3
                        and all(math.isfinite(float(value)) for value in offset),
                        "WING_AIM_OFFSET_BAD|bay=%s|slot=%s" %
                        (row["bay_index"], slot))


def _require_unique_bay_guids(data):
    guids = [row.get("cue_guid") for row in data.get("bay_plan", [])]
    require(all(guids), "BAY_CUE_GUID_MISSING|bays=%s" %
            [row.get("bay_index") for row in data.get("bay_plan", []) if not row.get("cue_guid")])
    require(len(guids) == len(set(guids)), "BAY_CUE_GUID_DUPLICATE")


def fixture_label(config, bay_index, look_name, slot):
    return "%s B%02d %s %s" % (
        config["fixture_label_prefix"], int(bay_index), look_name, slot)


def expand_bay(config, bay_row):
    look_name = bay_row["look"]
    scale = float(bay_row["level_scale"])
    mirror_roles = set(bay_row.get("mirror_roles", []))
    overrides = bay_row.get("instrument_overrides", {})
    expanded = []
    for source in config["looks"][look_name]["instruments"]:
        row = copy.deepcopy(source)
        if row["role"] in mirror_roles:
            row["transform"]["location_cm"][1] *= -1.0
            row["transform"]["rotation_rpy_deg"][2] *= -1.0
        fixture_override = copy.deepcopy(overrides.get(row["slot"], {}))
        override_location = fixture_override.pop("location_cm", None)
        if override_location is not None:
            row["transform"]["location_cm"] = [float(value) for value in override_location]
        row.update(fixture_override)
        row["intensity"] = float(row["intensity"]) * scale
        row["label"] = fixture_label(config, bay_row["bay_index"], look_name, row["slot"])
        row["bay_index"] = int(bay_row["bay_index"])
        row["look"] = look_name
        row["authored_kind"] = "LIGHT"
        row["distance_keying"] = copy.deepcopy(config["distance_keying"])
        expanded.append(row)
        if row["role"] == "PRACTICAL":
            visible = row["visible_mesh"]
            expanded.append({
                "slot": row["slot"] + "_BODY",
                "paired_slot": row["slot"],
                "role": "PRACTICAL_BODY",
                "authored_kind": "PROP",
                "label": fixture_label(
                    config, bay_row["bay_index"], look_name, row["slot"] + "_BODY"),
                "bay_index": int(bay_row["bay_index"]),
                "look": look_name,
                "mesh": visible["mesh"],
                "style": visible["style"],
                "emissive": bool(visible["emissive"]),
                "transform": {
                    "location_cm": list(row["transform"]["location_cm"]),
                    "rotation_rpy_deg": list(visible["rotation_rpy_deg"]),
                    "scale": list(visible["scale"]),
                },
                "cast_shadows": False,
            })
    return expanded


# --------------------------------------------------------------------------
# TUNE 4 (specs/LIGHTING_LOOKS_P04_TUNE1.md, "TUNE 4" sections): fence-socket
# hosting, beams through torn/half tarp bays, one flare sweep, PPV report.
#
# Identity rule: every cue is resolved by CueGuid. Labels are only compared
# after a GUID resolve, as a drift guard; no code path finds a cue by label.
#
# Frame rule (declaration-proven): a Station-anchored attachment is placed at
# RelativeTransform * WingPair.OccurrenceOffset * route(Wing.DistanceCm)
# (InfinityStagePassageActor.cpp:1646-1649). Lights here and FV3FB fence props
# are both Station-anchored (this file _make_light; fb_workflow.py:695), so a
# socket on a post anchored to cue A lands in cue B's frame by adding the
# station-x difference read from the fence plan's own anchors. The runtime
# refuses if either cue's OccurrenceOffset is not identity.
#
# Intermittency/brevity use the existing keyed-intensity route the looks use:
# FInfinityStageLightDrama strike-on-approach with AfterPass=Extinguish and a
# GUID-seeded ignition stutter (InfinityStageLightDrama.h:38-76,
# InfinityStageLightDrama.cpp:24-59), evaluated against camera route distance
# at Wing.DistanceCm + RelativeTransform.X (InfinityStagePassageActor.cpp:1650-1660).
# The flare pan is the same struct's SlowMove, which follows the Show master
# clock, not distance (InfinityStageLightDrama.h:78-104).
# --------------------------------------------------------------------------
SOCKET_HOSTED_ROLES = ("LOW_SIDE", "PRACTICAL", "FENCE_BEAM", "FLARE_SWEEP")
TUNE4_ADDED_ROLES = ("FENCE_BEAM", "FLARE_SWEEP")
BEAM_SOCKET = "SOCKET_Back_01"
BEAM_VARIANTS = ("tarp_torn", "tarp_half")
DRAMA_OVERRIDE_FIELDS = (
    "strike_distance_cm", "strike_ramp_cm", "ignition_stutter", "after_pass",
    "after_pass_distance_cm", "decay_distance_cm", "slow_move",
    "pan_amplitude_degrees", "tilt_amplitude_degrees", "period_seconds",
    "phase_from_identity", "phase_cycles",
)
PPV_FIELDS = (
    "bloom_intensity", "bloom_threshold", "lens_flare_intensity",
    "lens_flare_threshold", "lens_flare_bokeh_size", "lens_flare_tint",
    "auto_exposure_method", "auto_exposure_bias",
)
PPV_CHANGE_FIELDS = ("bloom_intensity", "lens_flare_intensity", "lens_flare_threshold")


def _hex_guid(value, label):
    text = str(value or "")
    require(len(text) == 32 and all(c in "0123456789ABCDEF" for c in text)
            and any(c != "0" for c in text),
            "%s_GUID_INVALID|value=%r" % (label, value))
    return text


def _range_pair(value, label, lo_min=None):
    require(isinstance(value, list) and len(value) == 2, "%s_RANGE_BAD" % label)
    lo = _finite(value[0], label)
    hi = _finite(value[1], label)
    require(lo <= hi and (lo_min is None or lo >= lo_min), "%s_RANGE_BAD" % label)
    return lo, hi


def _validate_tune4_fixture(row, label):
    require(row.get("type") == "SPOT", "%s_NOT_SPOT" % label)
    require(row.get("intensity_units") in ("CANDELAS", "LUMENS"), "%s_UNITS" % label)
    require(_finite(row.get("intensity"), label) > 0.0, "%s_INTENSITY" % label)
    require(_finite(row.get("attenuation_cm"), label) > 0.0, "%s_ATTENUATION" % label)
    rgb = row.get("color_rgb_linear", [])
    require(len(rgb) == 3 and all(_finite(v, label) >= 0.0 for v in rgb), "%s_RGB" % label)
    require(1000.0 <= _finite(row.get("temperature_kelvin"), label) <= 15000.0,
            "%s_TEMPERATURE" % label)
    inner = _finite(row.get("inner_cone_deg"), label)
    outer = _finite(row.get("outer_cone_deg"), label)
    require(0.0 <= inner <= outer <= 89.0, "%s_CONE" % label)
    require(_finite(row.get("volumetric_scattering"), label) > 0.0,
            "%s_HAZE_OFF" % label)


def validate_tune4(t):
    require(isinstance(t.get("enabled"), bool), "TUNE4_ENABLED_UNDECLARED")
    for key in ("fence_plan", "fence_socket_sidecar", "tarp_holes"):
        require(isinstance(t.get(key), str) and t[key], "TUNE4_PATH_MISSING|key=" + key)
    require(str(t.get("tree_post_mesh", "")).startswith("/Game/"), "TUNE4_TREE_POST_MESH")
    require(_finite(t.get("live_position_tolerance_cm"), "TOL") > 0.0, "TUNE4_TOLERANCE")
    require(_finite(t.get("live_yaw_tolerance_deg"), "TOL") > 0.0, "TUNE4_TOLERANCE")
    hosted = t.get("socket_hosted_roles", {})
    require(set(hosted) == {"LOW_SIDE", "PRACTICAL"}, "TUNE4_HOSTED_ROLES")
    require(hosted["LOW_SIDE"] == ["SOCKET_Low_01", "SOCKET_Low_02"],
            "TUNE4_LOW_SOCKETS")
    require(hosted["PRACTICAL"] == ["SOCKET_Lamp_01", "SOCKET_Lamp_02",
                                    "SOCKET_Lamp_03", "SOCKET_Lamp_04"],
            "TUNE4_LAMP_SOCKETS")
    structure = t.get("structure_hosted_roles", [])
    require(set(structure) <= {"TOP", "BEAM"} and not set(structure) & set(hosted),
            "TUNE4_STRUCTURE_ROLES")
    beams = t.get("beams", {})
    require(beams.get("socket") == BEAM_SOCKET,
            "BEAM_SOCKET_NOT_BACK|socket=%s" % beams.get("socket"))
    variants = beams.get("eligible_variants", [])
    require(variants and set(variants) <= set(BEAM_VARIANTS),
            "BEAM_VARIANT_NOT_TORN_OR_HALF|variants=%s" % variants)
    require(isinstance(beams.get("seed"), int), "BEAM_SEED")
    require(isinstance(beams.get("count"), int) and beams["count"] >= 1, "BEAM_COUNT")
    require(isinstance(beams.get("max_per_host_cue"), int)
            and beams["max_per_host_cue"] >= 1, "BEAM_MAX_PER_CUE")
    _range_pair(beams.get("tear_height_window_m"), "BEAM_TEAR_WINDOW", 0.0)
    pitch = _range_pair(beams.get("pitch_window_deg"), "BEAM_PITCH_WINDOW")
    require(-45.0 <= pitch[0] and pitch[1] <= 15.0, "BEAM_PITCH_WINDOW_NOT_SHALLOW")
    _validate_tune4_fixture(beams.get("fixture", {}), "BEAM_FIXTURE")
    require(beams["fixture"].get("cast_shadows") is True,
            "BEAM_MUST_CAST_TO_BE_SHAPED_BY_TARP")
    inter = beams.get("intermittency", {})
    _range_pair(inter.get("strike_distance_cm"), "BEAM_STRIKE", 0.0)
    _range_pair(inter.get("strike_ramp_cm"), "BEAM_RAMP", 1.0)
    stutter = _range_pair(inter.get("ignition_stutter"), "BEAM_STUTTER", 0.0)
    require(stutter[1] <= 1.0, "BEAM_STUTTER_RANGE_BAD")
    _range_pair(inter.get("after_pass_distance_cm"), "BEAM_AFTER_PASS", 0.0)
    require(inter.get("after_pass") == "EXTINGUISH", "BEAM_AFTER_PASS_NOT_EXTINGUISH")
    require(isinstance(inter.get("flicker_materials"), list)
            and inter["flicker_materials"], "BEAM_FLICKER_SET")
    flare = t.get("flare_sweep", {})
    require(isinstance(flare.get("seed"), int), "FLARE_SEED")
    require(flare.get("socket") == "SOCKET_Top", "FLARE_SOCKET_NOT_TOP")
    require(flare.get("host_bays") and set(flare["host_bays"]) <= set(range(1, 7)),
            "FLARE_HOST_BAYS")
    _validate_tune4_fixture(flare.get("fixture", {}), "FLARE_FIXTURE")
    require(flare["fixture"].get("cast_shadows") is False, "FLARE_MUST_NOT_CAST")
    require(_finite(flare.get("camera_height_cm"), "FLARE") > 0.0, "FLARE_CAMERA_HEIGHT")
    require(_finite(flare.get("aim_lead_cm"), "FLARE") > 0.0, "FLARE_AIM_LEAD")
    drama = flare.get("drama", {})
    require(set(drama) <= set(DRAMA_OVERRIDE_FIELDS), "FLARE_DRAMA_FIELDS")
    require(drama.get("after_pass") == "EXTINGUISH" and drama.get("slow_move") is True,
            "FLARE_NOT_BRIEF_SWEEP")
    require(0.0 < _finite(drama.get("pan_amplitude_degrees"), "FLARE") <= 45.0,
            "FLARE_PAN_RANGE")
    ppv = t.get("ppv", {})
    require(ppv.get("change_flag") == "LIGHTING_LOOKS_ALLOW_PPV_CHANGE", "PPV_FLAG_NAME")
    require(set(ppv.get("requested_change", {})) <= set(PPV_CHANGE_FIELDS),
            "PPV_CHANGE_FIELDS")


def _config_relative(path, config_dir=None):
    base = config_dir or os.path.dirname(CONFIG_PATH)
    return os.path.normpath(os.path.join(base, path))


def _rotate_z(vector, yaw_deg):
    radians = math.radians(float(yaw_deg))
    c, s = math.cos(radians), math.sin(radians)
    x, y, z = (float(v) for v in vector)
    return [c * x - s * y, s * x + c * y, z]


def fence_model(config, plan, sidecar):
    """Validate the fence plan read at run time; return GUID-keyed geometry."""
    t = config["tune4"]
    require(plan.get("passage") == "P04", "FENCE_PLAN_NOT_P04")
    require(plan.get("authority", {}).get("kind") == "Show Prop attachments",
            "FENCE_PLAN_AUTHORITY_NOT_SHOW_PROPS")
    sockets = {}
    for row in sidecar.get("sockets", []):
        rotation = row.get("relative_rotation_deg", {})
        sockets[row["name"]] = {
            "location_cm": [float(v) for v in row["relative_location_cm"]],
            "rotation_rpy_deg": [float(rotation.get("roll", 0.0)),
                                 float(rotation.get("pitch", 0.0)),
                                 float(rotation.get("yaw", 0.0))],
        }
    required = list(plan.get("guards", {}).get("required_lighting_sockets", []))
    require(required and set(required) <= set(sockets),
            "FENCE_SOCKET_SIDECAR_MISSING|missing=%s" %
            ",".join(sorted(set(required) - set(sockets))))
    station_x = {}

    def note_station(anchor, passage_location):
        guid = _hex_guid(anchor.get("cue_guid"), "FENCE_ANCHOR")
        relative = [float(v) for v in anchor["relative_location_cm"]]
        require(abs(float(passage_location[1]) - relative[1]) < 1.0e-6
                and abs(float(passage_location[2]) - relative[2]) < 1.0e-6,
                "FENCE_ANCHOR_NOT_X_ONLY|cue=" + guid)
        value = float(passage_location[0]) - relative[0]
        previous = station_x.setdefault(guid, value)
        require(abs(previous - value) < 1.0e-6,
                "FENCE_STATION_INCONSISTENT|cue=%s|a=%s|b=%s" % (guid, previous, value))
        return guid, relative

    posts = []
    for post in plan.get("posts", []):
        guid, relative = note_station(post["anchor"], post["passage_local_transform_cm"]["location"])
        if not post.get("lighting_tree"):
            continue
        require(post.get("mesh") == t["tree_post_mesh"],
                "FENCE_TREE_POST_MESH|post=%s%s" % (post["side"], post["post_index"]))
        require(set(required) <= set(post.get("socket_names", [])),
                "FENCE_TREE_POST_SOCKETS|post=%s%s" % (post["side"], post["post_index"]))
        posts.append({
            "side": post["side"],
            "post_index": int(post["post_index"]),
            "anchor_cue_guid": guid,
            "relative_location_cm": relative,
            "yaw_deg": float(post["passage_local_transform_cm"]["rotation_deg"][2]),
            "passage_location_cm": [float(v) for v in
                                    post["passage_local_transform_cm"]["location"]],
            "mesh": post["mesh"],
        })
    bays = []
    for bay in plan.get("bays", []):
        guid, relative = note_station(bay["anchor"], bay["passage_local_transform_cm"]["location"])
        bays.append({
            "side": bay["side"],
            "bay": int(bay["bay"]),
            "variant": bay["variant"],
            "anchor_cue_guid": guid,
            "relative_location_cm": relative,
            "yaw_deg": float(bay["passage_local_transform_cm"]["rotation_deg"][2]),
            "passage_location_cm": [float(v) for v in
                                    bay["passage_local_transform_cm"]["location"]],
            "meshes": [row["mesh"] for row in bay.get("attachments", [])],
        })
    require({row["side"] for row in posts} == {"left", "right"},
            "FENCE_TREE_POSTS_NOT_BOTH_SIDES")
    return {
        "plan_run_id": plan.get("run_id"),
        "plan_status": plan.get("status"),
        "station_x": station_x,
        "tree_posts": posts,
        "bays": bays,
        "sockets": sockets,
        "required_sockets": required,
    }


def load_fence_model(config, config_dir=None):
    t = config["tune4"]
    plan_path = _config_relative(t["fence_plan"], config_dir)
    sidecar_path = _config_relative(t["fence_socket_sidecar"], config_dir)
    require(os.path.isfile(plan_path), "FENCE_PLAN_ABSENT|path=" + plan_path)
    require(os.path.isfile(sidecar_path), "FENCE_SOCKET_SIDECAR_ABSENT|path=" + sidecar_path)
    model = fence_model(config, _read_json(plan_path), _read_json(sidecar_path))
    model["plan_path"] = plan_path
    model["plan_sha256"] = _sha256_file(plan_path)
    model["sidecar_path"] = sidecar_path
    model["sidecar_sha256"] = _sha256_file(sidecar_path)
    holes_path = _config_relative(t["tarp_holes"], config_dir)
    require(os.path.isfile(holes_path), "TARP_HOLES_ABSENT|path=" + holes_path)
    holes = _read_json(holes_path)
    model["tear_rows"] = {variant: holes["rows"][variant]["tears_m"]
                          for variant in BEAM_VARIANTS}
    model["tarp_holes_sha256"] = _sha256_file(holes_path)
    return model


def _live_prop_match(cue, mesh, relative_location, yaw_deg, t):
    tolerance = float(t["live_position_tolerance_cm"])
    yaw_tolerance = float(t["live_yaw_tolerance_deg"])
    hits = []
    for attachment in cue.get("attachments", []):
        if str(attachment.get("kind", "")).upper() != "PROP":
            continue
        if str(attachment.get("mesh") or "").split(".", 1)[0] != mesh:
            continue
        location = attachment.get("relative_location_cm") or [math.inf] * 3
        if max(abs(float(a) - float(b)) for a, b in zip(location, relative_location)) > tolerance:
            continue
        delta = (float(attachment.get("relative_yaw_deg", 0.0)) - float(yaw_deg)) % 360.0
        if min(delta, 360.0 - delta) > yaw_tolerance:
            continue
        hits.append(attachment)
    return hits


def require_fence_live(config, model, cues):
    """Refuse unless every tree post and every beam bay's props are in the live Show.

    Matched by anchor CueGuid + Prop kind + mesh + relative pose (never label).
    """
    t = config["tune4"]
    by_guid = {str(cue["guid"]): cue for cue in cues}
    missing = []
    for post in model["tree_posts"]:
        cue = by_guid.get(post["anchor_cue_guid"])
        hits = [] if cue is None else _live_prop_match(
            cue, post["mesh"], post["relative_location_cm"], post["yaw_deg"], t)
        if len(hits) != 1:
            missing.append("post:%s%02d:%d" % (post["side"][0].upper(), post["post_index"], len(hits)))
            continue
        post["live_attachment_guid"] = str(hits[0]["guid"])
        if not bool(hits[0].get("enabled", True)):
            missing.append("post_disabled:%s%02d" % (post["side"][0].upper(), post["post_index"]))
    for bay in model["bays"]:
        if bay["variant"] not in config["tune4"]["beams"]["eligible_variants"]:
            continue
        cue = by_guid.get(bay["anchor_cue_guid"])
        bay["live_attachment_guids"] = []
        for mesh in bay["meshes"]:
            hits = [] if cue is None else _live_prop_match(
                cue, mesh, bay["relative_location_cm"], bay["yaw_deg"], t)
            if len(hits) != 1:
                missing.append("bay:%s%02d:%s:%d" % (
                    bay["side"][0].upper(), bay["bay"], mesh.rsplit("/", 1)[-1], len(hits)))
            else:
                bay["live_attachment_guids"].append(str(hits[0]["guid"]))
    require(not missing, "FENCE_PROPS_MISSING|count=%d|first=%s" %
            (len(missing), ",".join(missing[:8])))
    for guid in {post["anchor_cue_guid"] for post in model["tree_posts"]}:
        require(bool(by_guid[guid].get("occurrence_offset_identity", True)),
                "FENCE_ANCHOR_OCCURRENCE_OFFSET_NOT_IDENTITY|cue=" + guid)
    return model


def _socket_world(model, post, socket_name):
    socket = model["sockets"][socket_name]
    offset = _rotate_z(socket["location_cm"], post["yaw_deg"])
    location = [p + o for p, o in zip(post["passage_location_cm"], offset)]
    forward_yaw = (post["yaw_deg"] + socket["rotation_rpy_deg"][2]) % 360.0
    return location, forward_yaw


def _to_cue_frame(model, passage_location, cue_guid):
    require(cue_guid in model["station_x"], "FENCE_STATION_UNKNOWN|cue=" + cue_guid)
    return [passage_location[0] - model["station_x"][cue_guid],
            passage_location[1], passage_location[2]]


def _forward_from_rpy(rpy):
    pitch, yaw = math.radians(float(rpy[1])), math.radians(float(rpy[2]))
    return [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)]


def _centre_plane_aim(location, rpy):
    """The authored ray's crossing of y=0 (corridor centre plane), else 10 m out."""
    forward = _forward_from_rpy(rpy)
    if abs(forward[1]) > 1.0e-6 and forward[1] * float(location[1]) < 0.0:
        distance = -float(location[1]) / forward[1]
    else:
        distance = 1000.0
    return [float(location[i]) + distance * forward[i] for i in range(3)]


def _host_record(post, socket_name, cue_guid, socket_location_cue):
    return {
        "post": "%s%02d" % (post["side"][0].upper(), post["post_index"]),
        "post_anchor_cue_guid": post["anchor_cue_guid"],
        "post_attachment_guid": post.get("live_attachment_guid"),
        "socket": socket_name,
        "host_cue_guid": cue_guid,
        "socket_location_in_host_cue_cm": list(socket_location_cue),
    }


def _allocate_socket(model, used, side, passage_x, socket_names, label):
    posts = sorted((post for post in model["tree_posts"] if post["side"] == side),
                   key=lambda post: (abs(post["passage_location_cm"][0] - passage_x),
                                     post["passage_location_cm"][0]))
    for rank, post in enumerate(posts):
        for name in socket_names:
            key = (post["side"], post["post_index"], name)
            if key not in used:
                used[key] = label
                return post, name, rank
    raise LightingLooksError("SOCKET_HOST_EXHAUSTED|fixture=%s|side=%s" % (label, side))


def _tear_points(bay, tear_rows, window, inset=0.3):
    """Candidate aim points inside each tear, in passage-local cm.

    tarp_holes.json gives each tear as a polygon in metres, u along the bay
    from its start (bay-local x = u*100 - 200 cm, build_fence_bay.py:800) and
    z up. Candidates are the polygon's vertices and edge midpoints pulled
    ``inset`` of the way toward the centroid, so the aim lies inside the hole.
    """
    points = []
    for tear_index, polygon in enumerate(tear_rows):
        xs = [float(p[0]) for p in polygon]
        zs = [float(p[1]) for p in polygon]
        cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
        raw = [(float(p[0]), float(p[1])) for p in polygon]
        raw += [((float(a[0]) + float(b[0])) / 2.0, (float(a[1]) + float(b[1])) / 2.0)
                for a, b in zip(polygon, list(polygon[1:]) + [polygon[0]])]
        raw.append((cx, cz))
        for u, z in raw:
            u = u + (cx - u) * inset
            z = z + (cz - z) * inset
            if not window[0] <= z <= window[1]:
                continue
            local = _rotate_z([u * 100.0 - 200.0, 0.0, z * 100.0], bay["yaw_deg"])
            points.append({"tear": tear_index, "u_m": u, "z_m": z,
                           "passage_location_cm": [b + l for b, l in
                                                   zip(bay["passage_location_cm"], local)]})
    return points


def _beam_through(source_passage, inward_yaw_deg, tears, pitch_window, label):
    """Most-across shallow path: least yaw off the socket's inward normal within the pitch window."""
    best = None
    for tear in tears:
        rotation = _look_at_rpy(source_passage, tear["passage_location_cm"], label)
        off = abs(((rotation[2] - inward_yaw_deg) + 180.0) % 360.0 - 180.0)
        if not pitch_window[0] <= rotation[1] <= pitch_window[1] or off >= 89.0:
            continue
        key = (round(off, 6), abs(rotation[1]))
        if best is None or key < best[0]:
            best = (key, tear, rotation, off)
    require(best is not None, "BEAM_NO_SHALLOW_PATH|fixture=" + label)
    unused_key, tear, rotation, off = best
    del unused_key
    return tear, rotation, off


def _seeded(rng, pair):
    lo, hi = pair
    value = rng.random()
    return lo + (hi - lo) * value


def tune4_fixtures(config, model, target_rows, tear_rows_by_variant):
    """Relocate LOW_SIDE/PRACTICAL to sockets, add beams + one flare sweep.

    Mutates each target's fixtures in place; deterministic for a given config,
    fence plan and tear table (single draw per statement, fixed order).
    """
    import random

    t = config["tune4"]
    hosted = t["socket_hosted_roles"]
    used = {}
    moves = []
    for target in target_rows:
        guid = target["cue_guid"]
        station = model["station_x"].get(guid)
        require(station is not None, "TARGET_NOT_IN_FENCE_PLAN|cue=" + guid)
        lights = {row["slot"]: row for row in target["fixtures"]
                  if row["authored_kind"] == "LIGHT"}
        for row in target["fixtures"]:
            if row["authored_kind"] != "LIGHT" or row["role"] not in hosted:
                continue
            old = list(row["transform"]["location_cm"])
            side = "left" if old[1] < 0.0 else "right"
            post, socket_name, rank = _allocate_socket(
                model, used, side, station + old[0], hosted[row["role"]], row["label"])
            socket_passage, forward_yaw = _socket_world(model, post, socket_name)
            new = _to_cue_frame(model, socket_passage, guid)
            if row["role"] == "LOW_SIDE":
                aim = _centre_plane_aim(old, row["transform"]["rotation_rpy_deg"])
                row["transform"]["rotation_rpy_deg"] = _look_at_rpy(new, aim, row["label"])
                row["reaim_point_cm"] = aim
            elif row["type"] == "RECT":
                rpy = list(row["transform"]["rotation_rpy_deg"])
                row["transform"]["rotation_rpy_deg"] = [rpy[0], rpy[1], forward_yaw]
            row["transform"]["location_cm"] = new
            row["socket_host"] = _host_record(post, socket_name, guid, new)
            row["socket_host"]["nearest_rank"] = rank
            moves.append({"fixture": row["label"], "from_cm": old, "to_cm": new,
                          "moved_cm": math.dist(old, new), "socket_host": row["socket_host"]})
        for row in target["fixtures"]:
            if row.get("authored_kind") == "PROP" and row.get("paired_slot") in lights:
                light = lights[row["paired_slot"]]
                row["transform"]["location_cm"] = list(light["transform"]["location_cm"])
                row["socket_host"] = copy.deepcopy(light.get("socket_host"))

    beams_cfg = t["beams"]
    by_target = {row["cue_guid"]: row for row in target_rows}
    eligible = [bay for bay in model["bays"]
                if bay["variant"] in beams_cfg["eligible_variants"]
                and bay["anchor_cue_guid"] in by_target]
    def adjacent_tree_post(bay):
        posts = [post for post in model["tree_posts"] if post["side"] == bay["side"]
                 and abs(abs(post["passage_location_cm"][0] - bay["passage_location_cm"][0])
                         - 200.0) < 1.0e-3]
        require(len(posts) == 1, "BEAM_BAY_TREE_POST_COUNT|bay=%s%02d|count=%d" %
                (bay["side"][0].upper(), bay["bay"], len(posts)))
        return posts[0]

    rng = random.Random(int(beams_cfg["seed"]))
    hosts = sorted({bay["anchor_cue_guid"] for bay in eligible},
                   key=lambda guid: by_target[guid]["bay_index"])
    rng.shuffle(hosts)
    chosen = []
    per_host = {}
    for guid in hosts:
        options = sorted((bay for bay in eligible if bay["anchor_cue_guid"] == guid),
                         key=lambda bay: (bay["side"], bay["bay"]))
        rng.shuffle(options)
        for bay in options:
            if len(chosen) >= beams_cfg["count"]:
                break
            if per_host.get(guid, 0) >= beams_cfg["max_per_host_cue"]:
                break
            post = adjacent_tree_post(bay)
            if (post["side"], post["post_index"], BEAM_SOCKET) in used:
                continue  # one Back socket per tree post
            used[(post["side"], post["post_index"], BEAM_SOCKET)] = "reserved"
            chosen.append((bay, post))
            per_host[guid] = per_host.get(guid, 0) + 1
    require(len(chosen) == beams_cfg["count"],
            "BEAM_COUNT_UNREACHABLE|wanted=%d|eligible_hosts=%d" %
            (beams_cfg["count"], len(hosts)))
    chosen.sort(key=lambda pair: (by_target[pair[0]["anchor_cue_guid"]]["bay_index"],
                                  pair[0]["side"], pair[0]["bay"]))
    beams = []
    inter = beams_cfg["intermittency"]
    for bay, post in chosen:
        target = by_target[bay["anchor_cue_guid"]]
        key = (post["side"], post["post_index"], BEAM_SOCKET)
        slot = "FENCE_BEAM_%s%02d" % (bay["side"][0].upper(), bay["bay"])
        label = fixture_label(config, target["bay_index"], target["look"], slot)
        used[key] = label
        source_passage, inward_yaw = _socket_world(model, post, BEAM_SOCKET)
        tears = _tear_points(bay, tear_rows_by_variant[bay["variant"]],
                             beams_cfg["tear_height_window_m"])
        require(tears, "BEAM_NO_TEAR_IN_WINDOW|bay=%s%02d" % (bay["side"][0].upper(), bay["bay"]))
        tear, unused_rotation, yaw_off_normal = _beam_through(
            source_passage, inward_yaw, tears, beams_cfg["pitch_window_deg"], label)
        del unused_rotation
        source = _to_cue_frame(model, source_passage, target["cue_guid"])
        through = _to_cue_frame(model, tear["passage_location_cm"], target["cue_guid"])
        rotation = _look_at_rpy(source, through, label)
        fixture = copy.deepcopy(beams_cfg["fixture"])
        strike = _seeded(rng, inter["strike_distance_cm"])
        ramp = _seeded(rng, inter["strike_ramp_cm"])
        stutter = _seeded(rng, inter["ignition_stutter"])
        after = _seeded(rng, inter["after_pass_distance_cm"])
        flicker_index = rng.randrange(len(inter["flicker_materials"]))
        flicker_material = inter["flicker_materials"][flicker_index]
        fixture.update({
            "slot": slot,
            "role": "FENCE_BEAM",
            "authored_kind": "LIGHT",
            "label": label,
            "bay_index": target["bay_index"],
            "look": target["look"],
            "transform": {"location_cm": source, "rotation_rpy_deg": rotation},
            "flicker": {"mode": "SEEDED" if flicker_material else "STEADY",
                        "material": flicker_material},
            "distance_keying": copy.deepcopy(config["distance_keying"]),
            "drama": {"strike_distance_cm": round(strike, 3),
                      "strike_ramp_cm": round(ramp, 3),
                      "ignition_stutter": round(stutter, 4),
                      "after_pass": inter["after_pass"],
                      "after_pass_distance_cm": round(after, 3)},
            "fence_bay": {"side": bay["side"], "bay": bay["bay"], "variant": bay["variant"],
                          "live_attachment_guids": bay.get("live_attachment_guids", [])},
            "through_tear": {"tear": tear["tear"], "u_m": tear["u_m"], "z_m": tear["z_m"],
                             "in_host_cue_cm": through,
                             "yaw_off_fence_normal_deg": round(yaw_off_normal, 3),
                             "pitch_deg": round(rotation[1], 3)},
            "socket_host": _host_record(post, BEAM_SOCKET, target["cue_guid"], source),
        })
        casters = sorted((row for row in target["fixtures"]
                          if row["authored_kind"] == "LIGHT" and row.get("cast_shadows")
                          and row["role"] == "LOW_SIDE"),
                         key=lambda row: (float(row["intensity"]), row["slot"]))
        require(casters, "BEAM_SHADOW_SWAP_MISSING|cue=" + target["cue_guid"])
        casters[0]["cast_shadows"] = False
        casters[0]["shadow_swapped_to"] = slot
        fixture["shadow_swapped_from"] = casters[0]["slot"]
        target["fixtures"].append(fixture)
        beams.append(fixture)

    flare_cfg = t["flare_sweep"]
    flare_rng = random.Random(int(flare_cfg["seed"]))
    host_bays = sorted(flare_cfg["host_bays"])
    host_bay = host_bays[flare_rng.randrange(len(host_bays))]
    target = next(row for row in target_rows if row["bay_index"] == host_bay)
    station = model["station_x"][target["cue_guid"]]
    side = ("left", "right")[flare_rng.randrange(2)]
    slot = "FLARE_SWEEP"
    label = fixture_label(config, target["bay_index"], target["look"], slot)
    post, socket_name, rank = _allocate_socket(
        model, used, side, station, [flare_cfg["socket"]], label)
    socket_passage, unused_yaw = _socket_world(model, post, socket_name)
    del unused_yaw
    source = _to_cue_frame(model, socket_passage, target["cue_guid"])
    aim = [source[0] - float(flare_cfg["aim_lead_cm"]), 0.0, float(flare_cfg["camera_height_cm"])]
    flare = copy.deepcopy(flare_cfg["fixture"])
    flare.update({
        "slot": slot, "role": "FLARE_SWEEP", "authored_kind": "LIGHT", "label": label,
        "bay_index": target["bay_index"], "look": target["look"],
        "transform": {"location_cm": source,
                      "rotation_rpy_deg": _look_at_rpy(source, aim, label)},
        "flicker": {"mode": "STEADY", "material": None},
        "distance_keying": copy.deepcopy(config["distance_keying"]),
        "drama": copy.deepcopy(flare_cfg["drama"]),
        "aim_point_cm": aim,
        "socket_host": _host_record(post, socket_name, target["cue_guid"], source),
    })
    flare["socket_host"]["nearest_rank"] = rank
    target["fixtures"].append(flare)
    for target in target_rows:
        target["fixture_count"] = len(target["fixtures"])
        target["new_shadow_casters"] = sum(bool(row.get("cast_shadows"))
                                           for row in target["fixtures"]
                                           if row["authored_kind"] == "LIGHT")
        target["light_fixture_count"] = sum(row["authored_kind"] == "LIGHT"
                                            for row in target["fixtures"])
    return {"moves": moves, "beams": [row["label"] for row in beams],
            "flare_sweep": flare["label"], "socket_use": len(used)}


def require_socket_hosts(config, target_rows):
    """No light in a socket-hosted role may lack a socket host; beams only Back+torn/half."""
    structure = set(config["tune4"]["structure_hosted_roles"])
    for target in target_rows:
        for row in target["fixtures"]:
            if row["authored_kind"] != "LIGHT":
                continue
            if row["role"] in structure:
                continue
            host = row.get("socket_host")
            require(host and host.get("socket") and host.get("post"),
                    "LIGHT_WITHOUT_SOCKET_HOST|fixture=%s|role=%s" % (row["label"], row["role"]))
            require(host["host_cue_guid"] == target["cue_guid"],
                    "SOCKET_HOST_WRONG_CUE|fixture=" + row["label"])
            require(row["transform"]["location_cm"] == host["socket_location_in_host_cue_cm"],
                    "LIGHT_NOT_AT_SOCKET|fixture=" + row["label"])
            if row["role"] == "FENCE_BEAM":
                require(host["socket"] == BEAM_SOCKET,
                        "BEAM_NOT_FROM_BACK_SOCKET|fixture=%s|socket=%s" %
                        (row["label"], host["socket"]))
                require(row["fence_bay"]["variant"] in BEAM_VARIANTS,
                        "BEAM_NOT_IN_TORN_OR_HALF_BAY|fixture=%s|variant=%s" %
                        (row["label"], row["fence_bay"]["variant"]))
            elif host["socket"] == BEAM_SOCKET:
                raise LightingLooksError("NON_BEAM_ON_BACK_SOCKET|fixture=" + row["label"])


def ppv_change_gate(allow_flag, requested):
    """PPV is report-only unless the explicit flag is set."""
    if requested and not allow_flag:
        raise LightingLooksError(
            "PPV_CHANGE_NOT_ALLOWED|set LIGHTING_LOOKS_ALLOW_PPV_CHANGE=True|fields=" +
            ",".join(sorted(requested)))
    return bool(requested) and bool(allow_flag)


def resolve_p04_span(config, cues, passage_rows):
    """P04 cue GUIDs in Show order, via the PassageSettings row whose FirstCueGuid matches."""
    first_guid = config["p04_scope"]["passage_first_cue_guid"]
    rows = [row for row in passage_rows if str(row.get("first")) == first_guid]
    require(len(rows) == 1, "P04_PASSAGE_ROW_COUNT|count=%d" % len(rows))
    index = {str(cue["guid"]): position for position, cue in enumerate(cues)}
    require(first_guid in index and str(rows[0].get("last")) in index,
            "P04_SPAN_GUID_UNRESOLVED")
    first, last = index[first_guid], index[str(rows[0]["last"])]
    require(first <= last, "P04_SPAN_REVERSED")
    return [str(cue["guid"]) for cue in cues[first:last + 1]]


def require_outside_unchanged(before_rows_by_guid, after_rows_by_guid, target_guids):
    """The outside-target hash guard (same as _verify_applied) on plain or full rows."""
    before = _outside_hash(before_rows_by_guid, target_guids)
    after = _outside_hash(after_rows_by_guid, target_guids)
    require(before == after, "OUTSIDE_TARGET_SCOPE_CHANGED|before=%s|after=%s" %
            (before[:12], after[:12]))
    return before


def _plain_is_light(attachment):
    return str(attachment.get("kind", "")).upper() == "LIGHT"


def _plain_casts(attachment):
    return (_plain_is_light(attachment) and bool(attachment.get("enabled", True))
            and bool(attachment.get("lighting", {}).get("cast_shadows", False)))


def build_plain_plan(config, cues, passage_rows, fence=None):
    """Resolve targets by CueGuid only, prove scope/budget, and apply tune 4.

    ``passage_rows`` are the Show's PassageSettings as {"first","last"} GUIDs;
    the P04 shadow scope is the GUID span, never a label pattern. ``fence`` is
    the live-checked fence model (required when tune 4 is enabled).
    """
    validate_config(config)
    cue_guids = [str(cue.get("guid", "")) for cue in cues]
    require(all(cue_guids) and len(cue_guids) == len(set(cue_guids)),
            "CUE_GUIDS_INVALID_OR_DUPLICATE")
    attachment_guids = [str(att.get("guid", "")) for cue in cues
                        for att in cue.get("attachments", [])]
    require(all(attachment_guids) and len(attachment_guids) == len(set(attachment_guids)),
            "ATTACHMENT_GUIDS_INVALID_OR_DUPLICATE")
    span = resolve_p04_span(config, cues, passage_rows)
    span_set = set(span)
    index_by_guid = {str(cue["guid"]): position for position, cue in enumerate(cues)}

    target_rows = []
    target_guid_set = set()
    for bay in config["bay_plan"]:
        cue_guid = bay["cue_guid"]
        require(cue_guid in index_by_guid, "TARGET_CUE_GUID_ABSENT|guid=" + cue_guid)
        require(cue_guid in span_set, "TARGET_CUE_OUTSIDE_P04|guid=" + cue_guid)
        show_index = index_by_guid[cue_guid]
        cue = cues[show_index]
        require(str(cue.get("label")) == bay["expected_label"],
                "TARGET_LABEL_MISMATCH|guid=%s|expected=%s|actual=%s" %
                (cue_guid, bay["expected_label"], cue.get("label")))
        target_guid_set.add(cue_guid)
        fixtures = expand_bay(config, bay)
        current_lights = [att for att in cue.get("attachments", []) if _plain_is_light(att)]
        target_rows.append({
            "bay_index": bay["bay_index"],
            "look": bay["look"],
            "level_scale": bay["level_scale"],
            "show_index": show_index,
            "cue_label": cue["label"],
            "cue_guid": cue_guid,
            "existing_lights": len(current_lights),
            "existing_enabled_lights": sum(bool(att.get("enabled", True)) for att in current_lights),
            "existing_shadow_casters": sum(_plain_casts(att) for att in current_lights),
            "fixtures": fixtures,
            "fixture_count": len(fixtures),
            "new_shadow_casters": sum(bool(row["cast_shadows"])
                                      for row in fixtures if row["authored_kind"] == "LIGHT"),
            "light_fixture_count": sum(row["authored_kind"] == "LIGHT" for row in fixtures),
            "practical_prop_count": sum(row["authored_kind"] == "PROP" for row in fixtures),
        })
    require(len(target_guid_set) == 6, "TARGET_GUIDS_NOT_UNIQUE")

    tune4 = None
    if config.get("tune4", {}).get("enabled"):
        require(fence is not None, "FENCE_INPUTS_REQUIRED")
        require_fence_live(config, fence, cues)
        tune4 = tune4_fixtures(config, fence, target_rows, fence["tear_rows"])
        require_socket_hosts(config, target_rows)

    new_labels = [row["label"] for target in target_rows for row in target["fixtures"]]
    require(len(new_labels) == len(set(new_labels)), "NEW_LABELS_DUPLICATE")
    current_labels = {str(att.get("label", "")) for cue in cues
                      for att in cue.get("attachments", [])}
    clashes = sorted(current_labels.intersection(new_labels))
    require(not clashes, "PROTOTYPE_ALREADY_PRESENT|labels=" + ",".join(clashes))

    before = sum(_plain_casts(att) for cue in cues if str(cue["guid"]) in span_set
                 for att in cue.get("attachments", []))
    removed = sum(row["existing_shadow_casters"] for row in target_rows)
    added = sum(row["new_shadow_casters"] for row in target_rows)
    after = before - removed + added
    cap = int(config["shadow_budget"]["cap"])
    require(after <= before,
            "SHADOW_BUDGET_EXCEEDED|before=%d|after=%d|removed=%d|added=%d"
            % (before, after, removed, added))
    require(after <= cap, "SHADOW_CAP_EXCEEDED|after=%d|cap=%d" % (after, cap))
    return {
        "targets": target_rows,
        "target_cue_guids": sorted(target_guid_set),
        "fixture_count": sum(row["fixture_count"] for row in target_rows),
        "light_fixture_count": sum(row["light_fixture_count"] for row in target_rows),
        "practical_prop_count": sum(row["practical_prop_count"] for row in target_rows),
        "existing_lights_disabled": sum(row["existing_lights"] for row in target_rows),
        "shadow": {
            "p04_before": before,
            "p04_after": after,
            "target_before": removed,
            "target_after": added,
            "cap": cap,
            "budget_ok": after <= before and after <= cap,
        },
        "p04_span_guids": span,
        "tune4": tune4,
        "fence": None if fence is None else {
            "plan_path": fence.get("plan_path"), "plan_sha256": fence.get("plan_sha256"),
            "plan_run_id": fence.get("plan_run_id"), "plan_status": fence.get("plan_status"),
            "sidecar_sha256": fence.get("sidecar_sha256"),
            "fence_prop_guids": sorted(
                [post["live_attachment_guid"] for post in fence["tree_posts"]]
                + [guid for bay in fence["bays"] for guid in bay.get("live_attachment_guids", [])]),
        },
    }


def apply_plain_state(config, cues, passage_rows, fence=None):
    """Offline model of the narrowly scoped mutation; used by the harness."""
    plan = build_plain_plan(config, cues, passage_rows, fence)
    result = copy.deepcopy(cues)
    record = {"targets": {}}
    by_guid = {str(cue["guid"]): cue for cue in result}
    for target in plan["targets"]:
        cue = by_guid[target["cue_guid"]]
        record["targets"][target["cue_guid"]] = copy.deepcopy(cue["attachments"])
        for attachment in cue["attachments"]:
            if _plain_is_light(attachment):
                attachment["enabled"] = False
        for fixture in target["fixtures"]:
            cue["attachments"].append({
                "guid": "NEW-%02d-%s" % (target["bay_index"], fixture["slot"]),
                "label": fixture["label"],
                "kind": "Light" if fixture["authored_kind"] == "LIGHT" else "Prop",
                "enabled": True,
                "lighting": {
                    "cast_shadows": bool(fixture.get("cast_shadows", False)),
                    "intensity": float(fixture.get("intensity", 0.0)),
                    "role": fixture["role"],
                },
            })
    return result, record, plan


def revert_plain_state(cues, record):
    result = copy.deepcopy(cues)
    by_guid = {str(cue["guid"]): cue for cue in result}
    require(set(record["targets"]).issubset(by_guid), "REVERT_TARGET_MISSING")
    for cue_guid, attachments in record["targets"].items():
        by_guid[cue_guid]["attachments"] = copy.deepcopy(attachments)
    return result


def _asset_id(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def _guid_text(value):
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()
        except Exception:  # noqa: BLE001 - wrapper variants differ.
            pass
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def _valid_guid_text(value):
    compact = "".join(character for character in str(value).upper()
                      if character in "0123456789ABCDEF")
    return len(compact) == 32 and any(character != "0" for character in compact)


def _enum_member(enum_type, name):
    candidates = (name, name.upper(), name.title().replace("_", ""))
    for candidate in candidates:
        if hasattr(enum_type, candidate):
            return getattr(enum_type, candidate)
    raise LightingLooksError("ENUM_MEMBER_MISSING|enum=%s|name=%s" % (enum_type, name))


def _dirty_census():
    return {
        "content": sorted(_asset_id(package)
                          for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(_asset_id(package)
                       for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _require_context():
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
    require(project.rstrip("\\/") == EXPECTED_PROJECT.rstrip("\\/"),
            "WRONG_PROJECT|actual=" + project)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None and _asset_id(world) == EXPECTED_WORLD,
            "WRONG_WORLD|actual=" + str(_asset_id(world)))
    sequence_library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if sequence_library is not None:
        require(sequence_library.get_current_level_sequence() is None, "SEQUENCER_IS_OPEN")
    require(_dirty_census() == {"content": [], "maps": []},
            "DIRTY_BEFORE|census=" + _canonical(_dirty_census()))
    actor_class = getattr(unreal, "Actor", None)
    if actor_class is not None:
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, actor_class)
        stray = sorted(actor.get_actor_label() for actor in actors
                       if actor.get_actor_label().startswith("ZZ_"))
        require(not stray, "STRAY_ZZ_ACTORS|labels=" + ",".join(stray))
    return world


def _is_light(attachment):
    return attachment.get_editor_property("kind") == _enum_member(
        unreal.InfinityAttachmentKind, "LIGHT")


def _attachment_row(attachment):
    return S.attachment_state(attachment, _guid_text)


def _attachment_rows(attachments):
    return [_attachment_row(attachment) for attachment in attachments]


def _state_differences(before, after, path=""):
    return S.state_differences(before, after, path)


def _require_attachment_rows_equal(actual, expected, message):
    differences = _state_differences(expected, actual)
    require(not differences, "%s|differences=%s" %
            (message, _canonical(differences)))


def _rows_hash(rows):
    return _state_hash(rows)


def _pair_attachments(cue):
    pair = cue.get_editor_property("wing_pair")
    return list(pair.get_editor_property("attachments"))


def _set_pair_attachments(show, cue_index, attachments):
    cues = list(show.get_editor_property("cues"))
    cue = cues[cue_index]
    pair = cue.get_editor_property("wing_pair")
    pair.set_editor_property("attachments", list(attachments))
    cue.set_editor_property("wing_pair", pair)
    cues[cue_index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _plain_cues(show):
    rows = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        attachments = []
        for attachment in _pair_attachments(cue):
            settings = attachment.get_editor_property("lighting")
            transform = S._transform_state(attachment.get_editor_property("relative_transform"))
            is_prop = attachment.get_editor_property("kind") == _enum_member(
                unreal.InfinityAttachmentKind, "PROP")
            attachments.append({
                "guid": _guid_text(attachment.get_editor_property("attachment_guid")),
                "label": str(attachment.get_editor_property("label")),
                "kind": "Light" if _is_light(attachment) else ("Prop" if is_prop else str(
                    attachment.get_editor_property("kind"))),
                "enabled": bool(attachment.get_editor_property("enabled")),
                "mesh": _asset_id(S._object_path(attachment.get_editor_property("mesh"))),
                "relative_location_cm": transform["location"],
                "relative_yaw_deg": _quat_yaw_deg(transform["rotation_xyzw"]),
                "lighting": {"cast_shadows": bool(settings.get_editor_property("cast_shadows"))},
            })
        occurrence = S._transform_state(
            cue.get_editor_property("wing_pair").get_editor_property("occurrence_offset"))
        rows.append({
            "show_index": index,
            "guid": _guid_text(cue.get_editor_property("cue_guid")),
            "label": str(cue.get_editor_property("label")),
            "attachments": attachments,
            "occurrence_offset_identity": _transform_is_identity(occurrence),
        })
    return rows


def _quat_yaw_deg(xyzw):
    """Yaw of a quaternion (fence props carry pure yaw)."""
    x, y, z, w = (float(v) for v in xyzw)
    return math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


def _transform_is_identity(state, tolerance=1.0e-4):
    return (all(abs(v) <= tolerance for v in state["location"])
            and all(abs(a - b) <= tolerance
                    for a, b in zip(state["rotation_xyzw"], [0.0, 0.0, 0.0, 1.0]))
            and all(abs(v - 1.0) <= tolerance for v in state["scale"]))


def _plain_passages(show):
    return [{"first": _guid_text(row.get_editor_property("first_cue_guid")),
             "last": _guid_text(row.get_editor_property("last_cue_guid")),
             "label": str(row.get_editor_property("label"))}
            for row in show.get_editor_property("passage_settings")]


def _live_fence_sockets(config, fence):
    """Read the imported tree-post mesh's sockets; require they match the sidecar."""
    mesh = unreal.load_asset(config["tune4"]["tree_post_mesh"])
    require(mesh is not None, "FENCE_TREE_POST_MESH_NOT_LOADED")
    rows = {}
    for name in fence["required_sockets"]:
        socket = mesh.find_socket(name)
        require(socket is not None, "FENCE_SOCKET_LIVE_MISSING|socket=" + name)
        location = socket.get_editor_property("relative_location")
        rotation = socket.get_editor_property("relative_rotation")
        live = [float(location.x), float(location.y), float(location.z)]
        live_yaw = float(rotation.yaw)
        want = fence["sockets"][name]
        yaw_error = ((live_yaw - want["rotation_rpy_deg"][2]) + 180.0) % 360.0 - 180.0
        require(max(abs(a - b) for a, b in zip(live, want["location_cm"])) <= 0.01
                and abs(yaw_error) <= 0.01,
                "FENCE_SOCKET_LIVE_MISMATCH|socket=%s|live=%s|yaw=%s" % (name, live, live_yaw))
        rows[name] = {"location_cm": live, "yaw_deg": live_yaw}
    return rows


def _all_pair_rows(show):
    result = {}
    for cue in show.get_editor_property("cues"):
        guid = _guid_text(cue.get_editor_property("cue_guid"))
        result[guid] = _attachment_rows(_pair_attachments(cue))
    return result


def _show_index_by_guid(show, cue_guid):
    matches = [index for index, cue in enumerate(show.get_editor_property("cues"))
               if _guid_text(cue.get_editor_property("cue_guid")) == cue_guid]
    require(len(matches) == 1,
            "CUE_GUID_RESOLVE_COUNT|guid=%s|count=%d" % (cue_guid, len(matches)))
    return matches[0]


def _make_transform(row):
    location = row["transform"]["location_cm"]
    roll, pitch, yaw = row["transform"]["rotation_rpy_deg"]
    scale = row["transform"].get("scale", [1.0, 1.0, 1.0])
    return unreal.Transform(
        location=unreal.Vector(*location),
        rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw),
        scale=unreal.Vector(*scale),
    )


def _look_at_rpy(source, target, label):
    """Return an Unreal X-forward look-at rotation in pair-local space."""
    dx = float(target[0]) - float(source[0])
    dy = float(target[1]) - float(source[1])
    dz = float(target[2]) - float(source[2])
    horizontal = math.hypot(dx, dy)
    require(horizontal > 1.0e-6 or abs(dz) > 1.0e-6,
            "TOP_AIM_ZERO_VECTOR|fixture=" + str(label))
    pitch = math.degrees(math.atan2(dz, horizontal))
    yaw = math.degrees(math.atan2(dy, dx))
    return [0.0, pitch, yaw]


def _apply_live_top_aims(show, plan):
    """Aim tops and explicitly targeted accents at live wing panel positions.

    Both the lights and these panel locations are authored in pair-local space,
    so the resulting look-at rotation remains exact after the pair is placed on
    the P04 route. This deliberately replaces the JSON prototype's stale fixed
    rotations; the Show is read fresh immediately before DRY/APPLY.
    """
    cues = list(show.get_editor_property("cues"))
    for target in plan["targets"]:
        cue = cues[target["show_index"]]
        pair = cue.get_editor_property("wing_pair")
        panels = {
            "L": pair.get_editor_property("left"),
            "R": pair.get_editor_property("right"),
        }
        target["top_aims"] = []
        target["accent_aims"] = []
        for fixture in target["fixtures"]:
            explicit_side = fixture.get("aim_wing_side")
            if fixture["role"] != "TOP" and explicit_side is None:
                continue
            if explicit_side is None:
                side = fixture["slot"].rsplit("_", 1)[-1]
                offset = [0.0, 0.0, 0.0]
                destination = target["top_aims"]
                source_name = "live Show panel local_transform"
            else:
                side = "L" if explicit_side == "LEFT" else "R"
                offset = [float(value) for value in fixture["aim_offset_pair_cm"]]
                destination = target["accent_aims"]
                source_name = "live Show panel local_transform plus pair-space accent offset"
            require(side in panels,
                    "WING_AIM_SIDE_UNKNOWN|fixture=" + fixture["label"])
            panel_transform = panels[side].get_editor_property("local_transform")
            panel_location = panel_transform.translation
            target_location = [
                float(panel_location.x) + offset[0],
                float(panel_location.y) + offset[1],
                float(panel_location.z) + offset[2],
            ]
            source_location = [float(value)
                               for value in fixture["transform"]["location_cm"]]
            rotation = _look_at_rpy(source_location, target_location, fixture["label"])
            fixture["transform"]["rotation_rpy_deg"] = rotation
            aim = {
                "fixture": fixture["label"],
                "panel": "LEFT" if side == "L" else "RIGHT",
                "source": source_name,
                "source_relative_cm": source_location,
                "target_relative_cm": target_location,
                "target_offset_pair_cm": offset,
                "rotation_rpy_deg": rotation,
            }
            if explicit_side is None:
                fixture["live_top_aim"] = copy.deepcopy(aim)
            else:
                fixture["live_accent_aim"] = copy.deepcopy(aim)
            destination.append(aim)
        require(len(target["top_aims"]) == 2,
                "TOP_AIM_COUNT|cue=%s|actual=%d" %
                (target["cue_label"], len(target["top_aims"])))
    return plan


def _make_blank_light():
    attachment = unreal.InfinityCueAttachment()
    attachment.set_editor_property("label", unreal.Text("P04 LOOK GUID SCRATCH"))
    attachment.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "LIGHT"))
    attachment.set_editor_property("enabled", False)
    attachment.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    settings = unreal.InfinityStageLightSettings()
    settings.set_editor_property("type", _enum_member(unreal.InfinityStageLightType, "SPOT"))
    settings.set_editor_property("intensity_units", _enum_member(
        unreal.InfinityStageLightIntensityUnits, "CANDELAS"))
    settings.set_editor_property("intensity", 0.0)
    settings.set_editor_property("cast_shadows", False)
    settings.set_editor_property("cast_volumetric_shadow", False)
    attachment.set_editor_property("lighting", settings)
    return attachment


def _make_light(row, materials):
    attachment = unreal.InfinityCueAttachment()
    attachment.set_editor_property("label", unreal.Text(row["label"]))
    attachment.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "LIGHT"))
    attachment.set_editor_property("enabled", True)
    attachment.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    attachment.set_editor_property("relative_transform", _make_transform(row))
    settings = unreal.InfinityStageLightSettings()
    settings.set_editor_property("type", _enum_member(unreal.InfinityStageLightType, row["type"]))
    settings.set_editor_property("intensity_units", _enum_member(
        unreal.InfinityStageLightIntensityUnits, row["intensity_units"]))
    settings.set_editor_property("intensity", float(row["intensity"]))
    rgb = row["color_rgb_linear"]
    settings.set_editor_property("color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    settings.set_editor_property("use_temperature", True)
    settings.set_editor_property("temperature_kelvin", float(row["temperature_kelvin"]))
    settings.set_editor_property("attenuation_radius_cm", float(row["attenuation_cm"]))
    settings.set_editor_property("cast_shadows", bool(row["cast_shadows"]))
    settings.set_editor_property("cast_volumetric_shadow",
                                 bool(row.get("cast_volumetric_shadow", False)))
    settings.set_editor_property("volumetric_scattering_intensity",
                                 float(row["volumetric_scattering"]))
    settings.set_editor_property("source_radius_cm", 2.0 if row["role"] != "PRACTICAL" else 4.0)
    settings.set_editor_property("soft_source_radius_cm", 8.0 if row["role"] != "PRACTICAL" else 12.0)
    if row["type"] == "SPOT":
        settings.set_editor_property("inner_cone_angle_degrees", float(row["inner_cone_deg"]))
        settings.set_editor_property("outer_cone_angle_degrees", float(row["outer_cone_deg"]))
    if row["type"] == "RECT":
        settings.set_editor_property("rect_source_width_cm", float(row["rect_source_width_cm"]))
        settings.set_editor_property("rect_source_height_cm", float(row["rect_source_height_cm"]))
    material_path = row["flicker"]["material"]
    if material_path:
        settings.set_editor_property("light_function_material", materials[material_path])
    drama = settings.get_editor_property("drama")
    keying = row["distance_keying"]
    drama.set_editor_property("strike_on_approach", True)
    drama.set_editor_property("strike_distance_cm", float(keying["strike_distance_cm"]))
    drama.set_editor_property("strike_ramp_cm", float(keying["ramp_distance_cm"]))
    drama.set_editor_property("ignition_stutter", 0.0)
    drama.set_editor_property("unstruck_intensity_scale",
                              float(keying["unstruck_intensity_scale"]))
    drama.set_editor_property("after_pass", _enum_member(
        unreal.InfinityLightAfterPass, keying["after_pass"]))
    drama.set_editor_property("slow_move", False)
    for name, value in sorted(row.get("drama", {}).items()):
        require(name in DRAMA_OVERRIDE_FIELDS, "DRAMA_FIELD_UNKNOWN|field=" + name)
        if name == "after_pass":
            value = _enum_member(unreal.InfinityLightAfterPass, value)
        elif isinstance(value, bool):
            value = bool(value)
        else:
            value = float(value)
        drama.set_editor_property(name, value)
    settings.set_editor_property("drama", drama)
    attachment.set_editor_property("lighting", settings)
    return attachment


def _make_prop(row, practical_meshes):
    attachment = unreal.InfinityCueAttachment()
    attachment.set_editor_property("label", unreal.Text(row["label"]))
    attachment.set_editor_property("kind", _enum_member(unreal.InfinityAttachmentKind, "PROP"))
    attachment.set_editor_property("enabled", True)
    attachment.set_editor_property("anchor", _enum_member(unreal.InfinityAttachmentAnchor, "STATION"))
    attachment.set_editor_property("relative_transform", _make_transform(row))
    attachment.set_editor_property("mesh", practical_meshes[row["mesh"]])
    return attachment


def _overwrite_vessel(vessel, template):
    minted = _guid_text(vessel.get_editor_property("attachment_guid"))
    require(_valid_guid_text(minted), "MINTED_GUID_INVALID|guid=" + minted)
    for name in ("label", "kind", "enabled", "actor_class", "mesh", "anchor",
                 "relative_transform", "lighting", "effect", "trigger_distance_cm"):
        vessel.set_editor_property(name, template.get_editor_property(name))
    require(_guid_text(vessel.get_editor_property("attachment_guid")) == minted,
            "MINTED_GUID_CHANGED")
    return vessel


def _materials(config):
    paths = {row["flicker"]["material"]
             for look in config["looks"].values()
             for row in look["instruments"] if row["flicker"]["material"]}
    if config.get("tune4", {}).get("enabled"):
        paths.update(path for path in
                     config["tune4"]["beams"]["intermittency"]["flicker_materials"] if path)
    paths = sorted(paths)
    loaded = {}
    for path in paths:
        asset = unreal.load_asset(path)
        require(asset is not None, "FLICKER_MATERIAL_MISSING|asset=" + path)
        loaded[path] = asset
    return loaded


def _practical_meshes(config):
    paths = sorted({row["visible_mesh"]["mesh"]
                    for look in config["looks"].values()
                    for row in look["instruments"] if row["role"] == "PRACTICAL"})
    loaded = {}
    for path in paths:
        asset = unreal.load_asset(path)
        require(asset is not None and asset.get_class().get_name() == "StaticMesh",
                "PRACTICAL_STATIC_MESH_MISSING|asset=" + path)
        loaded[path] = asset
    return loaded


def _package_file(package_path):
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    base = os.path.normpath(os.path.join(content, package_path[len("/Game/"):].replace("/", os.sep)))
    for extension in (".uasset", ".umap"):
        if os.path.isfile(base + extension):
            return base + extension
    raise LightingLooksError("PACKAGE_FILE_MISSING|package=" + package_path)


def _backup(prefix, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    root = os.path.join(project, "Backups", prefix + run)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (SHOW_PATH, EXPECTED_WORLD):
        source = _package_file(package)
        relative = package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1]
        destination = os.path.join(root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        source_hash = _sha256_file(source)
        require(source_hash == _sha256_file(destination),
                "BACKUP_HASH_MISMATCH|package=" + package)
        rows.append({"package": package, "source": source, "backup": destination,
                     "bytes": os.path.getsize(source), "sha256": source_hash})
    return {"root": root, "packages": rows}


def _materialize_p04(show):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = [actor for actor in subsystem.get_all_level_actors()
                if actor.get_class().get_name() == "InfinityStagePassageActor"
                and actor.get_actor_label().startswith("Passage 04")
                and actor.get_editor_property("show_asset") == show]
    require(len(passages) == 1, "P04_ACTOR_COUNT|count=%d" % len(passages))
    passage = passages[0]
    require(bool(passage.materialize_passage()), "P04_MATERIALIZE_FAILED")
    structures = [actor for actor in subsystem.get_all_level_actors()
                  if actor.get_class().get_name() == "InfinityStageStructureActor"
                  and actor.get_editor_property("passage") == passage]
    require(len(structures) == 1, "P04_STRUCTURE_COUNT|count=%d" % len(structures))
    structure = structures[0]
    require(bool(structure.materialize_structure()), "P04_STRUCTURE_REFIT_FAILED")
    return {
        "passage": passage.get_actor_label(),
        "structure": structure.get_actor_label(),
        "fixture_body_count": int(structure.get_editor_property("fixture_body_count")),
    }


def _save_narrow():
    census = _dirty_census()
    require(not (set(census["content"]) - {SHOW_PATH})
            and not (set(census["maps"]) - {EXPECTED_WORLD}),
            "OUT_OF_SCOPE_DIRTY_BEFORE_SAVE|census=" + _canonical(census))
    require(unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False),
            "SHOW_SAVE_FAILED")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(),
            "LEVEL_SAVE_FAILED")
    require(_dirty_census() == {"content": [], "maps": []},
            "DIRTY_AFTER_SAVE|census=" + _canonical(_dirty_census()))


def _queue_master_test(world, marker, run):
    require(_dirty_census() == {"content": [], "maps": []}, "DIRTY_BEFORE_TEST")
    unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + MASTER_TEST)
    unreal.log("%s_SAVED_MASTER_QUEUED|run=%s|test=%s|alone=true" % (marker, run, MASTER_TEST))


def _target_current(show, target):
    index = _show_index_by_guid(show, target["cue_guid"])
    cue = list(show.get_editor_property("cues"))[index]
    require(index == target["show_index"],
            "TARGET_INDEX_DRIFT|guid=%s|was=%d|now=%d" %
            (target["cue_guid"], target["show_index"], index))
    require(str(cue.get_editor_property("label")) == target["cue_label"],
            "TARGET_LABEL_DRIFT|guid=" + target["cue_guid"])
    return index, cue, _pair_attachments(cue)


def _outside_hash(all_rows, target_guids):
    return _state_hash({guid: rows for guid, rows in all_rows.items()
                        if guid not in set(target_guids)})


def _runtime_plan(show, config):
    plain = _plain_cues(show)
    fence = None
    live_sockets = None
    if config.get("tune4", {}).get("enabled"):
        # Read at run time: the fence plan may change in the rework.
        fence = load_fence_model(config)
        live_sockets = _live_fence_sockets(config, fence)
    plan = build_plain_plan(config, plain, _plain_passages(show), fence)
    plan["live_fence_sockets"] = live_sockets
    for target in plan["targets"]:
        require(plain[target["show_index"]]["occurrence_offset_identity"],
                "TARGET_OCCURRENCE_OFFSET_NOT_IDENTITY|cue=" + target["cue_guid"])
    _apply_live_top_aims(show, plan)
    for target in plan["targets"]:
        cue = list(show.get_editor_property("cues"))[target["show_index"]]
        target["before_rows"] = _attachment_rows(_pair_attachments(cue))
        target["before_hash"] = _rows_hash(target["before_rows"])
        target["expected_new_labels"] = [row["label"] for row in target["fixtures"]]
    return plan


def _mutate_apply(show, plan, materials, practical_meshes):
    cues = list(show.get_editor_property("cues"))
    target_guids = set(plan["target_cue_guids"])
    span = set(plan["p04_span_guids"])
    scratch_candidates = []
    for index, cue in enumerate(cues):
        guid = _guid_text(cue.get_editor_property("cue_guid"))
        if guid not in target_guids and guid in span:
            scratch_candidates.append((index, cue))
    require(scratch_candidates, "P04_SCRATCH_CUE_MISSING")
    scratch_index, scratch_cue = scratch_candidates[-1]
    scratch_original = _pair_attachments(scratch_cue)
    scratch_before = _attachment_rows(scratch_original)
    scratch_light_count = sum(_is_light(item) for item in scratch_original)
    needed = max(target["existing_lights"] + target["fixture_count"]
                 for target in plan["targets"])
    padding = max(0, needed - scratch_light_count)
    preexisting_guids = {_guid_text(item.get_editor_property("attachment_guid"))
                         for cue in cues for item in _pair_attachments(cue)}

    original_targets = {
        target["show_index"]: _pair_attachments(cues[target["show_index"]])
        for target in plan["targets"]
    }
    original_enabled = {
        _guid_text(attachment.get_editor_property("attachment_guid")):
            bool(attachment.get_editor_property("enabled"))
        for attachments in original_targets.values() for attachment in attachments
        if _is_light(attachment)
    }
    try:
        _set_pair_attachments(show, scratch_index,
                              scratch_original + [_make_blank_light() for _ in range(padding)])
        fresh_cues = list(show.get_editor_property("cues"))
        changed = show.replicate_light_attachments(
            fresh_cues[scratch_index].get_editor_property("cue_guid"),
            [fresh_cues[target["show_index"]].get_editor_property("cue_guid")
             for target in plan["targets"]])
        require(int(changed) == 6, "REPLICATION_TARGET_COUNT|count=%s" % changed)
        _set_pair_attachments(show, scratch_index, scratch_original)

        _require_attachment_rows_equal(
            _attachment_rows(_pair_attachments(
                list(show.get_editor_property("cues"))[scratch_index])),
            scratch_before, "SCRATCH_NOT_RESTORED_EXACTLY")

        added_guids = set()
        for target in plan["targets"]:
            index, unused_cue, replicated = _target_current(show, target)
            del unused_cue
            vessels = [item for item in replicated if _is_light(item)]
            start = target["existing_lights"]
            stop = start + target["fixture_count"]
            require(len(vessels) >= stop,
                    "MINTED_SLOT_COUNT|cue=%s|need=%d|actual=%d" %
                    (target["cue_label"], stop, len(vessels)))
            new_vessels = vessels[start:stop]
            original = original_targets[index]
            modified_original = []
            for attachment in original:
                if _is_light(attachment):
                    attachment.set_editor_property("enabled", False)
                modified_original.append(attachment)
            authored = []
            for vessel, fixture in zip(new_vessels, target["fixtures"]):
                minted = _guid_text(vessel.get_editor_property("attachment_guid"))
                require(minted not in preexisting_guids and minted not in added_guids,
                        "MINTED_GUID_NOT_FRESH|guid=" + minted)
                template = (_make_light(fixture, materials)
                            if fixture["authored_kind"] == "LIGHT"
                            else _make_prop(fixture, practical_meshes))
                authored.append(_overwrite_vessel(vessel, template))
                added_guids.add(minted)
            _set_pair_attachments(show, index, modified_original + authored)
            target["added"] = [
                {"guid": _guid_text(item.get_editor_property("attachment_guid")),
                 "label": str(item.get_editor_property("label"))}
                for item in authored
            ]
            target["after_rows"] = _attachment_rows(modified_original + authored)
            target["after_hash"] = _rows_hash(target["after_rows"])
            require([row["label"] for row in target["added"]] == target["expected_new_labels"],
                    "NEW_LABEL_ORDER_WRONG|cue=" + target["cue_label"])

        require(len(added_guids) == plan["fixture_count"],
                "ADDED_GUID_COUNT|expected=%d|actual=%d" %
                (plan["fixture_count"], len(added_guids)))
    except Exception:
        _set_pair_attachments(show, scratch_index, scratch_original)
        for target_index, attachments in original_targets.items():
            for attachment in attachments:
                if _is_light(attachment):
                    attachment.set_editor_property(
                        "enabled",
                        original_enabled[_guid_text(
                            attachment.get_editor_property("attachment_guid"))],
                    )
            _set_pair_attachments(show, target_index, attachments)
        _require_attachment_rows_equal(
            _attachment_rows(_pair_attachments(
                list(show.get_editor_property("cues"))[scratch_index])),
            scratch_before, "APPLY_ROLLBACK_SCRATCH_FAILED")
        for target in plan["targets"]:
            restored = _attachment_rows(_pair_attachments(
                list(show.get_editor_property("cues"))[target["show_index"]]))
            _require_attachment_rows_equal(
                restored, target["before_rows"],
                "APPLY_ROLLBACK_TARGET_FAILED|cue=" + target["cue_label"])
        raise


def _verify_applied(show, plan, outside_before):
    all_rows = _all_pair_rows(show)
    require(_outside_hash(all_rows, plan["target_cue_guids"]) == outside_before,
            "OUTSIDE_TARGET_SCOPE_CHANGED")
    fence_guids = set((plan.get("fence") or {}).get("fence_prop_guids", []))
    if fence_guids:
        before_by_guid = {row["guid"]: row for target in plan["targets"]
                          for row in target["before_rows"]}
        after_by_guid = {row["guid"]: row for rows in all_rows.values() for row in rows}
        for guid in sorted(fence_guids):
            require(guid in after_by_guid, "FENCE_PROP_LOST|guid=" + guid)
            if guid in before_by_guid:
                _require_attachment_rows_equal(
                    [after_by_guid[guid]], [before_by_guid[guid]],
                    "FENCE_PROP_CHANGED|guid=" + guid)
    for target in plan["targets"]:
        unused_index, unused_cue, attachments = _target_current(show, target)
        del unused_index, unused_cue
        rows = _attachment_rows(attachments)
        _require_attachment_rows_equal(
            rows, target["after_rows"],
            "APPLY_READBACK_MISMATCH|cue=" + target["cue_label"])
        original_count = len(target["before_rows"])
        original = attachments[:original_count]
        require(all(not bool(item.get_editor_property("enabled"))
                    for item in original if _is_light(item)),
                "EXISTING_LIGHT_STILL_ENABLED|cue=" + target["cue_label"])
    current_plan = build_plain_plan_for_applied(show, plan)
    require(current_plan["shadow_after"] == plan["shadow"]["p04_after"],
            "SHADOW_READBACK_MISMATCH|expected=%d|actual=%d" %
            (plan["shadow"]["p04_after"], current_plan["shadow_after"]))
    return current_plan


def build_plain_plan_for_applied(show, plan, span=None):
    plain = _plain_cues(show)
    span = set(span or plan["p04_span_guids"])
    shadow_after = sum(_plain_casts(att) for cue in plain if cue["guid"] in span
                       for att in cue["attachments"])
    labels = [att["label"] for cue in plain for att in cue["attachments"]
              if att["label"].startswith("P04 LOOK ")]
    return {"shadow_after": shadow_after, "prototype_labels": sorted(labels)}


def _mutate_revert(show, record):
    target_guids = record["plan"]["target_cue_guids"]
    outside_before = _outside_hash(_all_pair_rows(show), target_guids)
    foreign = _foreign_prop_guids(record)

    def own(attachments):
        kept = []
        for attachment in attachments:
            if _guid_text(attachment.get_editor_property("attachment_guid")).upper() in foreign:
                require(not _is_light(attachment), "FOREIGN_IS_LIGHT")
                continue
            kept.append(attachment)
        return kept
    current_by_index = {}
    current_enabled = {}
    try:
        for target in record["plan"]["targets"]:
            index, unused_cue, attachments = _target_current(show, target)
            del unused_cue
            current_by_index[index] = attachments
            for attachment in attachments:
                if _is_light(attachment):
                    current_enabled[_guid_text(
                        attachment.get_editor_property("attachment_guid"))] = bool(
                            attachment.get_editor_property("enabled"))
            current_rows = _attachment_rows(own(attachments))
            _require_attachment_rows_equal(
                current_rows, target["after_rows"],
                "REVERT_CURRENT_STATE_DRIFT|cue=" + target["cue_label"])
            added_guids = {row["guid"] for row in target["added"]}
            restored = []
            before_enabled = {row["guid"]: row["enabled"] for row in target["before_rows"]}
            removed = 0
            for attachment in attachments:
                guid = _guid_text(attachment.get_editor_property("attachment_guid"))
                if guid.upper() in foreign:
                    restored.append(attachment)  # W&T fence prop: kept as-is
                    continue
                if guid in added_guids:
                    removed += 1
                    continue
                require(guid in before_enabled,
                        "REVERT_UNKNOWN_ATTACHMENT|cue=%s|guid=%s" % (target["cue_label"], guid))
                if _is_light(attachment):
                    attachment.set_editor_property("enabled", bool(before_enabled[guid]))
                restored.append(attachment)
            require(removed == len(added_guids),
                    "REVERT_REMOVE_COUNT|cue=%s|expected=%d|actual=%d" %
                    (target["cue_label"], len(added_guids), removed))
            _set_pair_attachments(show, index, restored)
            _require_attachment_rows_equal(
                _attachment_rows(own(restored)), target["before_rows"],
                "REVERT_NOT_EXACT|cue=" + target["cue_label"])
        require(_outside_hash(_all_pair_rows(show), target_guids) == outside_before,
                "REVERT_OUTSIDE_TARGET_SCOPE_CHANGED")
        return outside_before
    except Exception:
        for index, attachments in current_by_index.items():
            for attachment in attachments:
                if _is_light(attachment):
                    attachment.set_editor_property(
                        "enabled",
                        current_enabled[_guid_text(
                            attachment.get_editor_property("attachment_guid"))],
                    )
            _set_pair_attachments(show, index, attachments)
        raise


def _p04_passage_actor(show):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = [actor for actor in subsystem.get_all_level_actors()
                if actor.get_class().get_name() == "InfinityStagePassageActor"
                and actor.get_actor_label().startswith("Passage 04")
                and actor.get_editor_property("show_asset") == show]
    require(len(passages) == 1, "P04_ACTOR_COUNT|count=%d" % len(passages))
    return passages[0]


def _p04_camera_rig(show):
    """The rig whose PassageActor is the P04 Passage (InfinityStageCameraRig.h:74)."""
    passage = _p04_passage_actor(show)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rigs = [actor for actor in subsystem.get_all_level_actors()
            if actor.get_class().get_name() == "InfinityStageCameraRig"
            and actor.get_editor_property("passage_actor") == passage]
    require(len(rigs) == 1, "P04_CAMERA_RIG_COUNT|count=%d" % len(rigs))
    return rigs[0]


def _pp_fields(settings):
    out = {}
    for name in PPV_FIELDS:
        try:
            override = bool(settings.get_editor_property("override_" + name))
        except Exception as error:  # noqa: BLE001 - report, never guess.
            override = "ERR %s" % type(error).__name__
        try:
            value = S._plain_struct_value(settings.get_editor_property(name))
        except Exception as error:  # noqa: BLE001
            value = "ERR %s" % type(error).__name__
        out[name] = {"override": override, "value": value}
    return out


def _ppv_report(show):
    """Read-only: P04 camera PP, every PostProcessVolume, height-fog volumetrics, cvars."""
    rig = _p04_camera_rig(show)
    camera = rig.get_editor_property("camera")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    volumes = []
    fogs = []
    for actor in subsystem.get_all_level_actors():
        name = actor.get_class().get_name()
        if name == "PostProcessVolume":
            volumes.append({
                "label": actor.get_actor_label(),
                "unbound": bool(actor.get_editor_property("unbound")),
                "enabled": bool(actor.get_editor_property("enabled")),
                "priority": float(actor.get_editor_property("priority")),
                "blend_weight": float(actor.get_editor_property("blend_weight")),
                "pp": _pp_fields(actor.get_editor_property("settings")),
            })
        elif name == "ExponentialHeightFog":
            component = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
            fogs.append({
                "label": actor.get_actor_label(),
                "volumetric_fog": bool(component.get_editor_property("volumetric_fog")),
                "volumetric_fog_extinction_scale": float(
                    component.get_editor_property("volumetric_fog_extinction_scale")),
                "volumetric_fog_scattering_distribution": float(
                    component.get_editor_property("volumetric_fog_scattering_distribution")),
            })
    cvars = {}
    for name in ("r.DefaultFeature.Bloom", "r.DefaultFeature.LensFlare",
                 "r.LensFlareQuality", "r.BloomQuality", "r.VolumetricFog"):
        try:
            cvars[name] = unreal.SystemLibrary.get_console_variable_int_value(name)
        except Exception as error:  # noqa: BLE001
            cvars[name] = "ERR %s" % type(error).__name__
    return {
        "camera_rig": rig.get_actor_label(),
        "camera_pp_blend_weight": float(camera.get_editor_property("post_process_blend_weight")),
        "camera_pp": _pp_fields(camera.get_editor_property("post_process_settings")),
        "post_process_volumes": volumes,
        "height_fogs": fogs,
        "cvars": cvars,
        "haze_ok": any(row["volumetric_fog"] for row in fogs),
    }


def _apply_ppv_change(show, requested, allow_flag):
    """Only with LIGHTING_LOOKS_ALLOW_PPV_CHANGE: override the P04 camera's own PP fields."""
    if not ppv_change_gate(allow_flag, requested):
        return None
    rig = _p04_camera_rig(show)
    camera = rig.get_editor_property("camera")
    settings = camera.get_editor_property("post_process_settings")
    before = _pp_fields(settings)
    for name, value in sorted(requested.items()):
        require(name in PPV_CHANGE_FIELDS, "PPV_FIELD_NOT_ALLOWED|field=" + name)
        settings.set_editor_property("override_" + name, True)
        settings.set_editor_property(name, float(value))
    rig.modify()
    camera.modify()
    camera.set_editor_property("post_process_settings", settings)
    after = _pp_fields(camera.get_editor_property("post_process_settings"))
    for name, value in requested.items():
        require(after[name]["override"] is True
                and abs(float(after[name]["value"]) - float(value)) < 1.0e-6,
                "PPV_CHANGE_READBACK|field=" + name)
    return {"camera_rig": rig.get_actor_label(), "before": before,
            "requested": dict(requested), "after": after}


def _revert_ppv_change(show, change):
    rig = _p04_camera_rig(show)
    require(rig.get_actor_label() == change["camera_rig"], "PPV_REVERT_RIG_DRIFT")
    camera = rig.get_editor_property("camera")
    settings = camera.get_editor_property("post_process_settings")
    for name in sorted(change["requested"]):
        before = change["before"][name]
        settings.set_editor_property("override_" + name, bool(before["override"]))
        settings.set_editor_property(name, float(before["value"]))
    rig.modify()
    camera.modify()
    camera.set_editor_property("post_process_settings", settings)
    after = _pp_fields(camera.get_editor_property("post_process_settings"))
    for name in change["requested"]:
        require(after[name] == change["before"][name], "PPV_REVERT_READBACK|field=" + name)


def _ppv_report_safe(show):
    try:
        return _ppv_report(show)
    except Exception as error:  # noqa: BLE001 - a report must not block the look.
        return {"error": "%s: %s" % (type(error).__name__, error)}


def _allow_ppv_change():
    return bool(globals().get("LIGHTING_LOOKS_ALLOW_PPV_CHANGE", False))


def _run(mode):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": mode, "run": run, "config": CONFIG_PATH}
    try:
        config = load_config()
        report["config_sha256"] = _sha256_file(CONFIG_PATH)
        world = _require_context()
        materials = _materials(config)
        practical_meshes = _practical_meshes(config)
        show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        requested_ppv = dict(config.get("tune4", {}).get("ppv", {}).get("requested_change", {}))

        if mode == "DRY":
            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
            plan = _runtime_plan(show, config)
            report.update({
                "ok": True,
                "plan": plan,
                "fixture_count": plan["fixture_count"],
                "light_fixture_count": plan["light_fixture_count"],
                "practical_prop_count": plan["practical_prop_count"],
                "existing_lights_disabled": plan["existing_lights_disabled"],
                "shadow": plan["shadow"],
                "mutated": False,
                "census": _dirty_census(),
                "materials": sorted(materials),
                "practical_meshes": sorted(practical_meshes),
                "ppv_live": _ppv_report_safe(show),
                "ppv_change": {"requested": requested_ppv,
                               "allowed": _allow_ppv_change(),
                               "would_apply": bool(requested_ppv) and _allow_ppv_change()},
            })
            _write_json(REPORT_PATH, report)
            unreal.log("LIGHTING_LOOKS_DRY_OK|run=%s|attachments=%d|lights=%d|practical_props=%d|disabled=%d|p04_shadow=%d->%d|mutated=0" %
                       (run, plan["fixture_count"], plan["light_fixture_count"],
                        plan["practical_prop_count"], plan["existing_lights_disabled"],
                        plan["shadow"]["p04_before"], plan["shadow"]["p04_after"]))
            return report

        if mode == "APPLY":
            require(not os.path.exists(RECORD_PATH), "ACTIVE_REVERT_RECORD_EXISTS")
            plan = _runtime_plan(show, config)
            all_before = _all_pair_rows(show)
            outside_before = _outside_hash(all_before, plan["target_cue_guids"])
            backup = _backup("PreLightingLooksP04-", run)
            record = {
                "schema_version": 1,
                "status": "prepared",
                "run": run,
                "config_sha256": report["config_sha256"],
                "backup": backup,
                "outside_before_hash": outside_before,
                "plan": plan,
            }
            _write_json(RECORD_PATH, record, exclusive=True)
            try:
                _mutate_apply(show, plan, materials, practical_meshes)
            except Exception:
                record["status"] = "failed_rolled_back_in_memory"
                failed_record = RECORD_PATH + ".failed-" + run
                _write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, failed_record)
                raise
            record["status"] = "mutated_verified"
            record["plan"] = plan
            _write_json(RECORD_PATH, record)
            verified = _verify_applied(show, plan, outside_before)
            record["ppv_live_before"] = _ppv_report_safe(show)
            record["ppv_change"] = _apply_ppv_change(show, requested_ppv, _allow_ppv_change())
            _write_json(RECORD_PATH, record)
            materialized = _materialize_p04(show)
            _save_narrow()
            readback_show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
            verified = _verify_applied(readback_show, plan, outside_before)
            record["status"] = "saved_readback_verified"
            record["saved_census"] = _dirty_census()
            record["materialized"] = materialized
            _write_json(RECORD_PATH, record)
            _queue_master_test(world, "LIGHTING_LOOKS", run)
            report.update({
                "ok": True,
                "fixture_count": plan["fixture_count"],
                "light_fixture_count": plan["light_fixture_count"],
                "practical_prop_count": plan["practical_prop_count"],
                "existing_lights_disabled": plan["existing_lights_disabled"],
                "shadow": plan["shadow"],
                "prototype_labels": verified["prototype_labels"],
                "tune4": plan.get("tune4"),
                "ppv_live_before": record["ppv_live_before"],
                "ppv_change": record["ppv_change"],
                "ppv_live_after": _ppv_report_safe(readback_show),
                "backup": backup,
                "record": RECORD_PATH,
                "materialized": materialized,
                "saved_master_test": "queued",
                "census": _dirty_census(),
            })
            _write_json(REPORT_PATH, report)
            unreal.log("LIGHTING_LOOKS_APPLY_OK|run=%s|attachments=%d|lights=%d|practical_props=%d|disabled=%d|p04_shadow=%d->%d|show_saved=1|level_saved=1|readback=1|saved_master=queued" %
                       (run, plan["fixture_count"], plan["light_fixture_count"],
                        plan["practical_prop_count"], plan["existing_lights_disabled"],
                        plan["shadow"]["p04_before"], plan["shadow"]["p04_after"]))
            return report

        require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_ABSENT")
        record = _read_json(RECORD_PATH)
        require(record.get("status") == "saved_readback_verified",
                "REVERT_RECORD_STATUS|status=" + str(record.get("status")))
        plan = record["plan"]
        span = resolve_p04_span(config, _plain_cues(show), _plain_passages(show))
        current = build_plain_plan_for_applied(show, plan, span)
        before_revert_shadow = current["shadow_after"]
        backup = _backup("PreLightingLooksP04Revert-", run)
        _mutate_revert(show, record)
        if record.get("ppv_change"):
            _revert_ppv_change(show, record["ppv_change"])
        expected_after = (before_revert_shadow - plan["shadow"]["target_after"]
                          + plan["shadow"]["target_before"])
        span_set = set(span)
        after_mutation = sum(_plain_casts(att) for cue in _plain_cues(show)
                             if cue["guid"] in span_set for att in cue["attachments"])
        require(after_mutation == expected_after,
                "REVERT_SHADOW_MISMATCH|expected=%d|actual=%d" %
                (expected_after, after_mutation))
        materialized = _materialize_p04(show)
        _save_narrow()
        readback_show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
        for target in plan["targets"]:
            unused_index, unused_cue, attachments = _target_current(readback_show, target)
            del unused_index, unused_cue
            foreign_ids = _foreign_prop_guids(record)
            _require_attachment_rows_equal(
                _attachment_rows([a for a in attachments if _guid_text(
                    a.get_editor_property("attachment_guid")).upper() not in foreign_ids]),
                target["before_rows"],
                "REVERT_READBACK_NOT_EXACT|cue=" + target["cue_label"])
        archived = RECORD_PATH + ".reverted-" + run
        os.rename(RECORD_PATH, archived)
        _queue_master_test(world, "LIGHTING_LOOKS_REVERT", run)
        report.update({
            "ok": True,
            "fixture_count_removed": plan["fixture_count"],
            "existing_lights_restored": plan["existing_lights_disabled"],
            "shadow": {"before_revert": before_revert_shadow,
                       "after_revert": after_mutation},
            "backup": backup,
            "record_archived": archived,
            "materialized": materialized,
            "saved_master_test": "queued",
            "census": _dirty_census(),
        })
        _write_json(REPORT_PATH, report)
        unreal.log("LIGHTING_LOOKS_REVERT_OK|run=%s|removed=%d|restored=%d|p04_shadow=%d->%d|show_saved=1|level_saved=1|readback=1|saved_master=queued" %
                   (run, plan["fixture_count"], plan["existing_lights_disabled"],
                    before_revert_shadow, after_mutation))
        return report
    except Exception as error:  # noqa: BLE001 - preserve a report for every stop.
        report["error"] = "%s: %s" % (type(error).__name__, error)
        report["census"] = _dirty_census() if unreal is not None else None
        _write_json(REPORT_PATH, report)
        if unreal is not None:
            unreal.log_error("LIGHTING_LOOKS_STOPPED|run=%s|mode=%s|%s" %
                             (run, mode, report["error"]))
        raise


def main(mode=None):
    selected = str(mode or globals().get("LIGHTING_LOOKS_MODE", "DRY")).upper()
    require(selected in VALID_MODES, "MODE_INVALID|mode=" + selected)
    require(unreal is not None, "UNREAL_REQUIRED_FOR_MODE|mode=" + selected)
    return _run(selected)


if unreal is not None:
    main()
