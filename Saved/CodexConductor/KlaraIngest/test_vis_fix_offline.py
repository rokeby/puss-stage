"""Offline positive/negative harness for P26 vis_fix + PIE case planner.

No Unreal, MCP, Content, or Blender. Run with system Python.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


V = load("vis_fix_under_test", HERE / "vis_fix.py")
P = load("vis_fix_probe_under_test", HERE / "vis_fix_pie_probe.py")


class Frame:
    def __init__(self, value):
        self.value = value


class Time:
    def __init__(self, value):
        self.frame_number = Frame(value)


class Key:
    def __init__(self, time, value):
        self.time = time
        self.value = value

    def get_time(self):
        return Time(self.time)

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = bool(value)


class Channel:
    def __init__(self, default=None, keys=()):
        self.default = default
        self.keys = [Key(*row) for row in keys]

    def has_default(self):
        return self.default is not None

    def get_default(self):
        return self.default

    def set_default(self, value):
        self.default = bool(value)

    def remove_default(self):
        self.default = None

    def get_keys(self):
        return self.keys


class Section:
    def __init__(self, start, end, channel):
        self.start = start
        self.end = end
        self.channel = channel

    def has_start_frame(self):
        return self.start is not None

    def has_end_frame(self):
        return self.end is not None

    def get_start_frame(self):
        return self.start

    def get_end_frame(self):
        return self.end

    def get_all_channels(self):
        return [self.channel]


class VisibilityTrack:
    def __init__(self, prop, sections, display="Visibility"):
        self.prop = prop
        self.path = prop
        self.sections = sections
        self.display = display

    def get_property_name(self):
        return self.prop

    def get_property_path(self):
        return self.path

    def set_property_name_and_path(self, prop, path):
        self.prop, self.path = str(prop), str(path)

    def get_display_name(self):
        return self.display

    def get_sections(self):
        return self.sections


class OtherTrack:
    pass


class Binding:
    def __init__(self, guid, name, tracks):
        self.guid, self.name, self.tracks = guid, name, tracks

    def get_id(self):
        return self.guid

    def get_display_name(self):
        return self.name

    def get_tracks(self):
        return self.tracks


class Sequence:
    def __init__(self, bindings):
        self.bindings = bindings

    def get_bindings(self):
        return self.bindings


class FakeUnreal:
    MovieSceneVisibilityTrack = VisibilityTrack


def sec(start, end, default, keys=()):
    return Section(start, end, Channel(default, keys))


def args(**overrides):
    value = {"mode": "DRY", "confirm": "DRY VISFIX", "run": "T", "tag": "S1",
             "sequence": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01",
             "file": "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_01.uasset"}
    value.update(overrides)
    return value


class ArgsControls(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(V.normalize_args(args())["tag"], "S1")

    def test_negative_confirm_and_unknown(self):
        with self.assertRaises(V.PlanError):
            V.normalize_args(args(confirm="APPLY VISFIX"))
        with self.assertRaises(V.PlanError):
            V.normalize_args(dict(args(), surprise=True))


class RepairControls(unittest.TestCase):
    def fixture(self):
        old_a = VisibilityTrack("bHiddenInGame", [sec(10, 20, True, [(12, True), (17, False)])])
        fixed = VisibilityTrack("bHidden", [sec(1, 3, False)])
        none = VisibilityTrack("None", [sec(4, 6, True)])
        old_b = VisibilityTrack("bHiddenInGame", [sec(30, 40, False)])
        seq = Sequence([Binding("A", "Mixed A", [OtherTrack(), old_a, fixed, none]),
                        Binding("B", "Mixed B", [old_b])])
        return seq, old_a, fixed, none, old_b

    def test_mixed_bindings_select_only_inert(self):
        sequence, _old_a, fixed, none, _old_b = self.fixture()
        rows = V.sequence_rows(sequence, FakeUnreal)
        plan = V.planned_rows(rows)
        self.assertEqual([(row["binding"], row["track_index"]) for row in plan], [("Mixed A", 1), ("Mixed B", 0)])
        self.assertEqual((fixed.prop, none.prop), ("bHidden", "None"))  # positive untouched controls

    def test_flip_and_exact_restore(self):
        _sequence, old, fixed, none, _old_b = self.fixture()
        before = V._track_state(old)
        expected = V.flip_state(before)
        self.assertEqual((expected["property"], expected["path"]), ("bHidden", "bHidden"))
        self.assertEqual(expected["sections"][0]["default"], False)
        self.assertEqual([row["value"] for row in expected["sections"][0]["keys"]], [False, True])
        V._set_state(old, expected)
        self.assertEqual(V._track_state(old), expected)
        V._set_state(old, before)
        self.assertEqual(V._track_state(old), before)
        self.assertEqual((fixed.prop, none.prop), ("bHidden", "None"))

    def test_negative_diff_and_key_drift(self):
        _sequence, old, _fixed, _none, _old_b = self.fixture()
        state = V._track_state(old)
        wrong = copy.deepcopy(state)
        wrong["sections"][0]["default"] = not wrong["sections"][0]["default"]
        self.assertTrue(V.state_diff(state, wrong))
        drifted = copy.deepcopy(state)
        drifted["sections"][0]["keys"][0]["time"] += 1
        with self.assertRaises(V.PlanError):
            V._set_state(old, drifted)


class ProbeControls(unittest.TestCase):
    def targets(self):
        state = {"property": "bHidden", "path": "bHidden", "display": "Visibility", "sections": [
            {"index": 0, "range": [10, 20], "default": False,
             "keys": [{"time": 15, "value": True}]},
        ]}
        return [{"id": "A:0", "binding_guid": "A", "binding": "Actor A", "track_index": 0,
                 "state": {}, "expected_after": state}]

    def test_inside_outside_and_key_evaluation(self):
        cases = P.build_cases(self.targets(), [0, 30], outside_hidden=False)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["outside"], {"frame": 9, "expected_hidden": False})
        # Midpoint is frame 14, before the visible=True key: visible=False => hidden=True.
        self.assertEqual(cases[0]["inside"], {"frame": 14, "expected_hidden": True})
        section = self.targets()[0]["expected_after"]["sections"][0]
        self.assertFalse(P.value_at(section, 14))
        self.assertTrue(P.value_at(section, 15))

    def test_negative_no_outside_and_no_value(self):
        targets = self.targets()
        targets[0]["expected_after"]["sections"][0]["range"] = [0, 30]
        with self.assertRaises(P.ProbeError):
            P.build_cases(targets, [0, 30])
        with self.assertRaises(P.ProbeError):
            P.value_at({"default": None, "keys": []}, 1)


class CreatorSourceControls(unittest.TestCase):
    FILES = [
        HERE / "klara_hookin.py", HERE / "klara_hookin_s6.py", HERE / "klara_reveal.py",
        HERE / "klara_void_s6.py", HERE.parent / "s4_hangar_hold.py", HERE.parent / "p18_sky_policy.py",
    ]

    def test_no_creator_binds_inert_property(self):
        for path in self.FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Attribute) and node.func.attr == "set_property_name_and_path"]
            pairs = [(node.args[0].value, node.args[1].value) for node in calls if len(node.args) >= 2 and
                     all(isinstance(arg, ast.Constant) and isinstance(arg.value, str) for arg in node.args[:2])]
            self.assertNotIn(("bHiddenInGame", "bHiddenInGame"), pairs, str(path))
            self.assertIn(("bHidden", "bHidden"), pairs, str(path))

    def test_visible_polarity_present(self):
        source = {path.name: path.read_text(encoding="utf-8") for path in self.FILES}
        self.assertIn("set_default(not bool(hidden))", source["klara_hookin.py"])
        self.assertIn("set_default(not bool(hidden))", source["klara_reveal.py"])
        self.assertIn("set_default(False)", source["klara_hookin_s6.py"])
        self.assertIn("set_default(False)", source["klara_void_s6.py"])
        self.assertIn("visibility_channel_value", source["s4_hangar_hold.py"])
        self.assertIn("channels[0].set_default(False)", source["p18_sky_policy.py"])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)))
    print("VISFIX_HARNESS|run=%d|failures=%d|errors=%d|positive_controls=6|negative_controls=6" %
          (result.testsRun, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
