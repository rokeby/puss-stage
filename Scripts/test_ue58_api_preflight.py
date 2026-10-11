#!/usr/bin/env python3
"""Positive and negative controls for ue58_api_preflight.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("ue58_api_preflight.py")
SPEC = importlib.util.spec_from_file_location("ue58_api_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
LINTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LINTER
SPEC.loader.exec_module(LINTER)


class PreflightTests(unittest.TestCase):
    def scan(self, source: str):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "tool.py"
            path.write_text(source, encoding="utf-8")
            return LINTER.scan_file(path)

    def test_positive_known_broken_surfaces_are_denied(self):
        source = """
import unreal
stamp = unreal.DateTime.now()
root = actor.get_root_component()
child = cls.is_child_of(base)
where = root.get_relative_location()
mode = unreal.MovieSceneKeyInterpolation.CUBIC
track.set_property_name_and_path("CurrentFocalLength", "CurrentFocalLength")
master.add_master_track(unreal.MovieSceneFadeTrack)
section.get_channels()
unreal.EditorAssetLibrary.get_dirty_content_packages()
"""
        surfaces = {finding.surface for finding in self.scan(source) if finding.status == "DENY"}
        expected = {
            "unreal.DateTime.now", "*.get_root_component", "*.is_child_of",
            "*.get_relative_location", "unreal.MovieSceneKeyInterpolation.CUBIC",
            'MovieSceneFloatTrack("CurrentFocalLength")', "*.add_master_track",
            "*.get_channels", "unreal.EditorAssetLibrary.get_dirty_content_packages",
        }
        self.assertTrue(expected <= surfaces, expected - surfaces)

    def test_positive_type_aware_transform_and_rotator_denials(self):
        findings = self.scan("""
import unreal
xf = unreal.MathLibrary.compose_transforms(a, b)
bad_rot = xf.rotator()
rot = unreal.Rotator()
bad_vec = rot.rotate_vector(v)
""")
        denied = {finding.surface for finding in findings if finding.status == "DENY"}
        self.assertIn("Transform.rotator", denied)
        self.assertIn("Rotator.rotate_vector", denied)

    def test_negative_working_replacements_are_not_denied(self):
        findings = self.scan("""
import unreal
xf = unreal.MathLibrary.compose_transforms(a, b)
good_rot = xf.rotation.rotator()
rot = unreal.Rotator()
good_vec = rot.quaternion().rotate_vector(v)
root = actor.get_editor_property("root_component")
where = root.get_editor_property("relative_location")
channels = section.get_all_channels()
track = master.add_track(unreal.MovieSceneFadeTrack)
mode = unreal.MovieSceneKeyInterpolation.AUTO
dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
""")
        self.assertFalse([finding for finding in findings if finding.status == "DENY"])

    def test_negative_unknown_is_informational_and_exit_zero(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "tool.py"
            path.write_text("import unreal\nunreal.FutureSubsystem.do_new_thing()\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = LINTER.main([str(path)])
            self.assertEqual(0, code)
            self.assertIn("UNKNOWN", output.getvalue())

    def test_positive_deny_makes_exit_one(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "tool.py"
            path.write_text("import unreal\nunreal.DateTime.now()\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = LINTER.main([str(path)])
            self.assertEqual(1, code)

    def test_positive_required_sweep_and_split_groom_calls(self):
        findings = self.scan("""
actor.set_actor_transform(xf)
component.set_groom_asset(groom, binding, True)
""")
        denied = {finding.surface for finding in findings if finding.status == "DENY"}
        self.assertEqual({"Actor.set_actor_transform", "GroomComponent.set_groom_asset(groom,binding,...)"}, denied)

    def test_positive_secondary_10_oct_wrapper_failures(self):
        findings = self.scan("""
import unreal
settings = unreal.MovieSceneSequencePlaybackSettings()
settings.restore_state = True
source_class = unreal.EditorAssetLibrary.load_blueprint_class("/Game/BP")
bad = isinstance(generated, source_class)
for key in channel.get_keys():
    key.remove()
""")
        denied = {finding.surface for finding in findings if finding.status == "DENY"}
        self.assertEqual({"MovieSceneSequencePlaybackSettings.restore_state",
                          "isinstance(..., UClass)", "MovieSceneScriptingKey.remove"}, denied)


if __name__ == "__main__":
    unittest.main(verbosity=2)
