"""Offline controls for Job 185 fixture-position comparison."""

import importlib.util
import pathlib
import sys
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent
CORE = HERE / "job185_fixture_probe_common.py"


def load_core():
    fake = types.ModuleType("unreal")
    fake.Paths = type("Paths", (), {
        "project_saved_dir": staticmethod(lambda: str(HERE.parents[2] / "Saved")),
        "convert_relative_path_to_full": staticmethod(str),
    })
    sys.modules["unreal"] = fake
    spec = importlib.util.spec_from_file_location("job185_fixture_probe_common_test", CORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixtureProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_core()

    def test_one_body_move_isolated(self):
        before = [[0, 0, 10], [100, 0, 20], [200, 0, 30]]
        after = [[0, 0, 10], [150, 0, 20], [200, 0, 30]]
        removed, added = self.core.unmatched(before, after)
        self.assertEqual(removed, [[100, 0, 20]])
        self.assertEqual(added, [[150, 0, 20]])

    def test_restored_multiset_has_no_delta(self):
        before = [[0, 0, 10], [100, 0, 20], [100, 0, 20]]
        missing, extra = self.core.unmatched(before, list(reversed(before)))
        self.assertEqual(missing, [])
        self.assertEqual(extra, [])

    def test_wrong_body_move_is_detected(self):
        before = [[0, 0, 0], [100, 0, 0]]
        after = [[0, 0, 0], [100, 25, 0]]
        removed, added = self.core.unmatched(before, after)
        delta = [added[0][i] - removed[0][i] for i in range(3)]
        self.assertNotEqual(delta, [50, 0, 0])

    def test_target_body_is_found_despite_unrelated_new_bodies(self):
        expected = [150, 0, 20]
        after = [[0, 0, 10], [150, 0, 20], [200, 0, 30], [999, 999, 999]]
        self.assertEqual(self.core.nearest_distance(expected, after), 0.0)

    def test_editor_transform_commit_uses_root_property_notification(self):
        source = CORE.read_text(encoding="utf-8")
        self.assertIn('actor.get_editor_property("root_component")', source)
        self.assertIn('root.set_editor_property(\n        "relative_location"', source)
        self.assertNotIn('actor.set_actor_location(', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
