"""Harness for stream_lowpass.py: synthetic sway + zero-mean jitter. Positive and negative controls.
Run: python test_stream_lowpass.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_lowpass as lp


def synth(n=120, v=50, jitter=0.008, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(n)[:, None, None] / 30.0
    base = rng.normal(size=(1, v, 3)).astype(np.float64)
    sway = 0.05 * np.sin(2 * np.pi * 0.3 * t) * np.ones((1, v, 3))          # slow 0.3 Hz sway, 5 cm
    jit = np.where(np.arange(n)[:, None, None] >= 40, 1.0, 0.0) * jitter * ((-1.0) ** np.arange(n))[:, None, None] \
        * rng.choice([-1.0, 1.0], size=(1, v, 3))                         # alternating sign = buzz, from frame 40
    return (base + sway + jit).astype(np.float32)


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.s = synth()
        self.src = self.root / "x_stream.f32"
        self.s.tofile(self.src)
        self.side = self.root / "x_stream.json"
        self.side.write_text(json.dumps({"vertices": 50, "first_frame": 1, "dtype": "float32",
                                         "layout": "frame-major xyz", "faces": []}))

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, out, *extra):
        return lp.main(["--src", str(self.src), "--sidecar", str(self.side), "--out", str(out), "--from", "40", *extra])

    def test_removes_buzz_keeps_sway(self):
        out = self.root / "y_stream.f32"
        self.assertEqual(self.run_main(out), 0)
        y = np.fromfile(out, dtype="<f4").reshape(self.s.shape)
        before = lp.metrics(self.s, [80])[81]
        after = lp.metrics(y, [80])[81]
        self.assertGreater(before["reversing"], 0.5)
        self.assertLess(after["reversing"], 0.05)
        sway = 0.05 * np.sin(2 * np.pi * 0.3 * np.arange(120) / 30.0)
        mean_y = y[60:110].mean(axis=1)[:, 0] - y[60:110].mean(axis=(0, 1))[0]
        self.assertGreater(np.corrcoef(mean_y, sway[60:110] - sway[60:110].mean())[0, 1], 0.99)   # sway kept

    def test_frames_before_from_bit_identical(self):
        out = self.root / "y_stream.f32"
        self.run_main(out)
        y = np.fromfile(out, dtype="<f4").reshape(self.s.shape)
        self.assertTrue(np.array_equal(y[:39], self.s[:39]))

    def test_no_seam_step(self):
        out = self.root / "y_stream.f32"
        self.run_main(out)
        y = np.fromfile(out, dtype="<f4").reshape(self.s.shape)
        steps = np.linalg.norm(np.diff(y[35:56].astype(np.float64), axis=0), axis=2).max(axis=1)
        raw = np.linalg.norm(np.diff(self.s[35:56].astype(np.float64), axis=0), axis=2).max(axis=1)
        self.assertLessEqual(steps.max(), raw.max() + 1e-6)          # the blend adds no step bigger than the raw ones

    def test_sidecar_written(self):
        out = self.root / "y_stream.f32"
        self.run_main(out)
        j = json.loads(out.with_suffix(".json").read_text())
        self.assertIn("lowpass", j)
        self.assertEqual(j["vertices"], 50)

    def test_neg_out_exists(self):
        out = self.root / "y_stream.f32"
        out.write_bytes(b"x")
        self.assertEqual(self.run_main(out), 2)

    def test_neg_out_equals_src(self):
        self.assertEqual(self.run_main(self.src), 2)

    def test_neg_partial_frame(self):
        with open(self.src, "ab") as fh:
            fh.write(b"\0" * 7)
        self.assertEqual(self.run_main(self.root / "z.f32"), 2)

    def test_neg_from_out_of_range(self):
        r = lp.main(["--src", str(self.src), "--sidecar", str(self.side), "--out", str(self.root / "q.f32"), "--from", "500"])
        self.assertEqual(r, 2)

    def test_neg_even_window(self):
        with self.assertRaises(ValueError):
            lp.lowpass(self.s, 40, 8, 0)

    def test_source_untouched(self):
        before = self.src.read_bytes()
        self.run_main(self.root / "y_stream.f32")
        self.assertEqual(self.src.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
