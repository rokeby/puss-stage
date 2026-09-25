#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

import music_analysis as analysis


def click_track(bpm: float, seconds: float, sample_rate: int = 11025) -> np.ndarray:
    samples = np.zeros(int(seconds * sample_rate), dtype=np.float32)
    pulse = np.hanning(101).astype(np.float32)
    interval = 60.0 / bpm
    for time_seconds in np.arange(0.5, seconds - 0.2, interval):
        start = int(time_seconds * sample_rate)
        samples[start : start + pulse.size] += pulse
    return samples


class MusicAnalysisGoldenTests(unittest.TestCase):
    def test_known_tempo_is_ranked(self) -> None:
        result = analysis.analyze_samples(click_track(120.0, 24.0), 11025)
        self.assertTrue(any(abs(item["bpm"] - 120.0) < 2.0 for item in result["tempoCandidates"][:5]))
        self.assertFalse(result["safety"]["cueScoreMutated"])

    def test_known_structural_boundary_is_proposed(self) -> None:
        sample_rate = 11025
        time = np.arange(sample_rate * 24, dtype=np.float32) / sample_rate
        rng = np.random.default_rng(1234)
        samples = np.where(time < 12.0, 0.25 * np.sin(2 * np.pi * 220 * time), 0.18 * rng.standard_normal(time.size)).astype(np.float32)
        result = analysis.analyze_samples(samples, sample_rate)
        self.assertTrue(any(abs(item["timeSeconds"] - 12.0) < 2.0 for item in result["majorChangeProposals"]))

    def test_silence_is_finite_and_has_no_tempo(self) -> None:
        result = analysis.analyze_samples(np.zeros(11025 * 8, dtype=np.float32), 11025)
        self.assertEqual(result["tempoCandidates"], [])
        self.assertTrue(np.isfinite(result["summary"]["rmsDb"]))

    def test_analysis_is_deterministic(self) -> None:
        samples = click_track(90.0, 18.0)
        self.assertEqual(
            analysis.analyze_samples(samples, 11025, source_name="repeat"),
            analysis.analyze_samples(samples, 11025, source_name="repeat"),
        )

    def test_fingerprint_changes_with_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "click.wav"
            samples = np.clip(click_track(60.0, 4.0) * 32767, -32768, 32767).astype("<i2")
            with wave.open(str(path), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(11025)
                writer.writeframes(samples.tobytes())
            first = analysis.file_fingerprints(path)
            with path.open("ab") as handle:
                handle.write(b"changed")
            second = analysis.file_fingerprints(path)
            self.assertNotEqual(first["sha256"], second["sha256"])


class ExpressiveAnalysisTest(unittest.TestCase):
    """The expressive layer must describe arcs, not just instants."""

    @staticmethod
    def _arc() -> np.ndarray:
        rate = 11025
        span = 20.0

        def tone(amplitude: float, freqs: list[float], noise: float = 0.0) -> np.ndarray:
            t = np.arange(int(span * rate)) / rate
            signal = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
            if noise:
                signal = signal + noise * np.random.default_rng(0).standard_normal(t.size)
            return signal * amplitude

        quiet = tone(0.06, [220.0])
        building = tone(1.0, [220.0, 440.0]) * np.linspace(0.06, 0.85, int(span * rate))
        intense = tone(0.9, [220.0, 440.0, 880.0, 1760.0], noise=0.25)
        releasing = tone(1.0, [220.0, 440.0]) * np.linspace(0.9, 0.05, int(span * rate))
        return np.concatenate([quiet, building, intense, releasing]).astype(np.float32)

    def setUp(self) -> None:
        self.result = analysis.analyze_samples(self._arc(), 11025, source_name="arc")

    def test_curves_are_well_formed(self) -> None:
        curves = self.result["featureCurves"]
        self.assertEqual(curves["rateHz"], analysis.CURVE_EXPORT_RATE_HZ)
        for name, values in curves["curves"].items():
            self.assertEqual(len(values), curves["sampleCount"], f"{name} length")
        for value in curves["curves"]["intensity"]:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_intensity_tracks_the_arc(self) -> None:
        intensity = np.array(self.result["featureCurves"]["curves"]["intensity"])
        quarter = intensity.size // 4
        means = [intensity[i * quarter : (i + 1) * quarter].mean() for i in range(4)]
        self.assertLess(means[0], means[1], "quiet should be below the build")
        self.assertLess(means[1], means[2], "the build should reach the intense span")
        self.assertLess(means[3], means[2], "the release should fall away")

    def test_sections_name_the_dynamics(self) -> None:
        sections = self.result["expressiveSections"]
        self.assertTrue(sections, "expected at least one expressive section")
        labels = [section["label"] for section in sections]
        self.assertIn("intense", labels)
        self.assertIn("releasing", labels)
        for section in sections:
            self.assertLess(section["startSeconds"], section["endSeconds"])
            self.assertEqual(section["state"], "Suggested")

    def test_analysis_remains_a_proposal(self) -> None:
        self.assertFalse(self.result["safety"]["cueScoreMutated"])
        self.assertTrue(self.result["safety"]["requiresArtistApproval"])


if __name__ == "__main__":
    unittest.main()
