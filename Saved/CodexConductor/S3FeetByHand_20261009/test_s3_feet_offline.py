"""Offline positive/negative harness. Does not import Unreal or touch project assets."""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s3_feet_core as C  # noqa: E402

positive = []
negative = []


def ok(name, fn):
    fn()
    positive.append(name)


def refuses(name, token, fn):
    try:
        fn()
    except C.Stop as exc:
        assert token in str(exc), (name, token, str(exc))
        negative.append(name)
        return
    raise AssertionError("negative control did not refuse: " + name)


CFG = {
    "mode": "DRY", "apply_xy": False, "max_delta_cm": 200.0,
    "min_z_delta_cm": 0.001, "rotation_tolerance_deg": 0.01,
    "scale_tolerance": 0.0001, "readback_tolerance_cm": 0.01,
    "root_sequence": C.ROOT_SEQUENCE, "world": C.WORLD, "confirm": "",
}
T0 = {"location": [10.0, 20.0, 30.0], "rotation": [0.0, 0.0, 179.999], "scale": [1.0, 1.0, 1.0]}
T1 = {"location": [11.0, 18.0, 42.0], "rotation": [0.0, 0.0, -180.001], "scale": [1.0, 1.0, 1.0]}


def channel(keys=None, default=0.0, has_default=True, raw="Location.Z_183"):
    return {"raw_name": raw, "keys": copy.deepcopy(keys or []),
            "has_default": has_default, "default": default if has_default else None}


def binding(kind="possessable", blend="ABSOLUTE"):
    channels = {}
    for name in C.TRANSFORM_CHANNELS:
        channels[name] = channel([[ ]][0], 0.0, True, name + "_183")
    channels["Location.Z"] = channel([{"frame": 0, "value": 10.0},
                                       {"frame": 100, "value": 20.0}], 4.0)
    return {"sequence_path": C.ROOT_SEQUENCE, "binding_guid": "A" * 32,
            "binding_display_name": "Shore01_M56 Shore", "kind": kind,
            "template_transform": copy.deepcopy(T0) if kind == "spawnable" else None,
            "transform_sections": [{"track_index": 0, "section_index": 0,
                                    "track_name": "Transform", "section_name": "Section",
                                    "blend_type": blend, "channels": channels}]}


ok("config accepts guarded defaults", lambda: C.validate_config(copy.deepcopy(CFG)))
ok("suffix normalisation", lambda: (_ for _ in ()).throw(AssertionError())
   if C.channel_base("Location.Z_183") != "Location.Z" else None)
ok("all six fixed labels", lambda: C.validate_target_labels(list(C.FIXED_LABELS)))
ok("job40 variants admitted", lambda: C.validate_target_labels(list(C.FIXED_LABELS) + ["P40 Shore Variant 01 (Shore04_F55)"]))
ok("original alias maps to Shore binding", lambda: (_ for _ in ()).throw(AssertionError())
   if "Shore01_M56 Shore" not in C.binding_aliases("Shore01_M56 Clam") else None)
ok("Shore05 exact alias avoids float hold", lambda: (_ for _ in ()).throw(AssertionError())
   if C.binding_aliases("Shore05_M53 Clam") != ("Shore05_M53 Clam",) else None)
ok("capture reports XY but applies Z only", lambda: (_ for _ in ()).throw(AssertionError())
   if C.capture_delta(T0, T1, CFG, "A")["applied_location_delta_cm"] != [0.0, 0.0, 12.0] else None)

cfg_xy = copy.deepcopy(CFG); cfg_xy["apply_xy"] = True
ok("capture opt-in applies XY", lambda: (_ for _ in ()).throw(AssertionError())
   if C.capture_delta(T0, T1, cfg_xy, "A")["applied_location_delta_cm"] != [1.0, -2.0, 12.0] else None)
ok("all keys offset", lambda: (_ for _ in ()).throw(AssertionError())
   if [x["value"] for x in C.shifted_channel(channel([{"frame": 0, "value": 1.0}, {"frame": 5, "value": 2.0}]), 3.0)["keys"]] != [4.0, 5.0] else None)
ok("unkeyed default offset", lambda: (_ for _ in ()).throw(AssertionError())
   if C.shifted_channel(channel([], 7.0), -2.0)["default"] != 5.0 else None)
ok("spawnable template offset", lambda: (_ for _ in ()).throw(AssertionError())
   if C.make_expected_binding(binding("spawnable"), [1.0, 2.0, 3.0])["template_transform"]["location"] != [11.0, 22.0, 33.0] else None)
ok("possessable has no template write", lambda: (_ for _ in ()).throw(AssertionError())
   if C.make_expected_binding(binding(), [0.0, 0.0, 5.0])["template_transform"] is not None else None)
ok("structure ignores values but retains frames", lambda: (_ for _ in ()).throw(AssertionError())
   if C.structural_binding(binding()) != C.structural_binding(C.make_expected_binding(binding(), [0.0, 0.0, 5.0])) else None)
ok("wrapped rotation equivalence", lambda: (_ for _ in ()).throw(AssertionError())
   if not C.transform_near(T0, T1, loc_tol=20.0, rot_tol=0.001) else None)

bad = copy.deepcopy(CFG); bad["mode"] = "BOGUS"
refuses("unknown mode", "MODE", lambda: C.validate_config(bad))
bad = copy.deepcopy(CFG); bad["apply_xy"] = 1
refuses("non-bool xy", "APPLY_XY_BOOL", lambda: C.validate_config(bad))
bad = copy.deepcopy(CFG); bad["max_delta_cm"] = 201.0
refuses("limit cannot exceed 200", "MAX_DELTA_LIMIT", lambda: C.validate_config(bad))
bad = copy.deepcopy(CFG); bad["world"] = "/Game/Wrong"
refuses("wrong configured world", "WORLD", lambda: C.validate_config(bad))
bad = copy.deepcopy(CFG); bad["root_sequence"] = "/Game/Master"
refuses("wrong configured sequence", "ROOT_SEQUENCE", lambda: C.validate_config(bad))
refuses("missing fixed target", "MISSING_FIXED_TARGETS", lambda: C.validate_target_labels(list(C.FIXED_LABELS[:-1])))
refuses("unexpected crowd target", "UNEXPECTED_TARGETS", lambda: C.validate_target_labels(list(C.FIXED_LABELS) + ["S3 Crowd 01"]))
refuses("duplicate label", "DUPLICATE_TARGET_LABEL", lambda: C.validate_target_labels(list(C.FIXED_LABELS) + [C.FIXED_LABELS[0]]))

t = copy.deepcopy(T1); t["rotation"][0] = 1.0
refuses("rotation change", "ROTATION_CHANGED", lambda: C.capture_delta(T0, t, CFG, "A"))
t = copy.deepcopy(T1); t["scale"][0] = 1.2
refuses("scale change", "SCALE_CHANGED", lambda: C.capture_delta(T0, t, CFG, "A"))
t = copy.deepcopy(T0)
refuses("z delta required", "Z_DELTA_REQUIRED", lambda: C.capture_delta(T0, t, CFG, "A"))
t = copy.deepcopy(T1); t["location"][2] = 231.0
refuses("delta axis over 200", "DELTA_AXIS_OVER_LIMIT", lambda: C.capture_delta(T0, t, CFG, "A"))
t = copy.deepcopy(T1); t["location"] = [160.0, 170.0, 31.0]
refuses("delta vector over 200", "DELTA_VECTOR_OVER_LIMIT", lambda: C.capture_delta(T0, t, CFG, "A"))
refuses("unkeyed missing default", "UNKEYED_CHANNEL_WITHOUT_DEFAULT", lambda: C.shifted_channel(channel([], None, False), 3.0))
refuses("relative section", "NON_ABSOLUTE_SECTION", lambda: C.make_expected_binding(binding(blend="RELATIVE"), [0.0, 0.0, 2.0]))
C.make_expected_binding(binding(blend="ADDITIVE"), [0.0, 0.0, 2.0])  # additive accepted (10 Oct live)
b = binding("spawnable"); b["template_transform"] = None
refuses("spawnable template required", "SPAWNABLE_TEMPLATE_MISSING", lambda: C.make_expected_binding(b, [0.0, 0.0, 2.0]))
refuses("unknown actor alias", "UNKNOWN_TARGET_LABEL", lambda: C.binding_aliases("Shore07_X Clam"))

source = open(os.path.join(HERE, "s3_feet_editor.py"), "r", encoding="utf-8").read()
for name, token in (
    ("no Sequencer editor library", "LevelSequenceEditorBlueprintLibrary"),
    ("no sequence player", "LevelSequencePlayer"),
    ("no map save", "save_map("),
    ("no Save All", "save_all"),
    ("no master load", '"/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_Master"'),
):
    if token in source:
        raise AssertionError(name + " token present: " + token)
    negative.append(name)

for name, token in (
    ("exact sequence save", "save_only_sequences"),
    ("backup before apply", 'backup_assets("PreS3Feet"'),
    ("backup before revert", 'backup_assets("PreS3FeetRevert"'),
    ("spawnable template route", "binding.get_object_template()"),
    ("map remains disposable", '"map_save_required": False'),
    ("explicit apply confirmation", 'cfg["confirm"] == "APPLY S3 FEET"'),
    ("explicit revert confirmation", 'cfg["confirm"] == "REVERT S3 FEET"'),
):
    assert token in source, (name, token)
    positive.append(name)

print("S3_FEET_OFFLINE_PASS|positive=%d/%d|negative=%d/%d|total=%d/%d" %
      (len(positive), len(positive), len(negative), len(negative),
       len(positive) + len(negative), len(positive) + len(negative)))
print(json.dumps({"positive": positive, "negative": negative}, indent=2))
