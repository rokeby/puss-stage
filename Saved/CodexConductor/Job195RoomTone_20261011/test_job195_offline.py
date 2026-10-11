"""Negative and positive offline harness for Job 195."""

import json
import os
import tempfile
import unittest
import wave

import job195_core as core


class Job195Tests(unittest.TestCase):
    def base(self, **changes):
        value = {
            "mode": "DRY", "run": "J195-DRY-TEST",
            "source_wav": "Content/InfinityStage/Audio/RoomTone/Cameron.wav",
        }
        value.update(changes)
        return value

    def test_positive_defaults(self):
        result = core.validate_args(self.base())
        self.assertEqual(result["asset_path"], "/Game/InfinityStage/Audio/RoomTone/SW_Cameron_RoomTone")
        self.assertTrue(result["enable_s6_dip"])

    def test_positive_apply_confirm(self):
        self.assertEqual(core.validate_args(self.base(mode="APPLY", run="J195-APPLY-TEST",
                                                      confirm="APPLY JOB195 ROOM TONE"))["mode"], "APPLY")

    def test_positive_revert_confirm(self):
        result = core.validate_args(self.base(mode="REVERT", run="J195-REVERT-TEST",
                                              source_wav="", record="records/a.json",
                                              confirm="REVERT JOB195 ROOM TONE"))
        self.assertEqual(result["record"], "records/a.json")

    def test_negative_bad_mode(self):
        with self.assertRaises(core.PlanError):
            core.validate_args(self.base(mode="GO"))

    def test_negative_apply_confirm(self):
        with self.assertRaises(core.PlanError):
            core.validate_args(self.base(mode="APPLY", run="J195-APPLY-TEST"))

    def test_negative_revert_record(self):
        with self.assertRaises(core.PlanError):
            core.validate_args(self.base(mode="REVERT", run="J195-REVERT-TEST",
                                         source_wav="", confirm="REVERT JOB195 ROOM TONE"))

    def test_negative_missing_source(self):
        with tempfile.TemporaryDirectory() as root:
            result = core.resolve_source(root, "missing.wav")
            self.assertEqual(result["status"], "MISSING")

    def test_negative_empty_directory(self):
        with tempfile.TemporaryDirectory() as root:
            result = core.resolve_source(root, root)
            self.assertEqual(result["status"], "EMPTY_DIRECTORY")

    def test_negative_ambiguous_directory(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("a.wav", "b.wav"):
                with wave.open(os.path.join(root, name), "wb") as handle:
                    handle.setparams((1, 2, 48000, 48, "NONE", ""))
                    handle.writeframes(b"\0\0" * 48)
            self.assertEqual(core.resolve_source(root, root)["status"], "AMBIGUOUS_DIRECTORY")

    def test_positive_wav_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "room.wav")
            with wave.open(path, "wb") as handle:
                handle.setparams((2, 2, 48000, 4800, "NONE", ""))
                handle.writeframes(b"\0\0\0\0" * 4800)
            result = core.resolve_source(root, path)
            self.assertEqual(result["status"], "READY")
            self.assertAlmostEqual(result["duration_s"], 0.1)
            self.assertEqual(result["channels"], 2)

    def test_positive_gain_outside_s6(self):
        self.assertEqual(core.gain_db(-18, -12, 0), -18)

    def test_positive_gain_full_s6(self):
        self.assertEqual(core.gain_db(-18, -12, 1), -30)

    def test_negative_positive_dip_cannot_boost(self):
        self.assertEqual(core.gain_db(-18, 12, 1), -18)

    def test_positive_disable_dip(self):
        self.assertEqual(core.gain_db(-18, -12, 1, False), -18)


if __name__ == "__main__":
    unittest.main(verbosity=2)

