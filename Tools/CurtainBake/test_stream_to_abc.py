from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_to_abc as recovery


class StreamToAbcHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.frames = np.asarray(
            [
                [[0.0, 0.0, 0.2], [1.0, 0.0, 0.2], [0.0, 0.0, 1.2], [1.0, 0.0, 1.2]],
                [[0.0, 0.1, 0.2], [1.0, 0.1, 0.2], [0.0, 0.1, 1.2], [1.0, 0.1, 1.2]],
                [[0.0, 0.2, 0.2], [1.0, 0.2, 0.2], [0.0, 0.2, 1.2], [1.0, 0.2, 1.2]],
            ],
            dtype="<f4",
        )
        self.stream = self.root / "synthetic.f32"
        self.frames.tofile(self.stream)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_positive_pc2_round_trip_preserves_world_vertices(self) -> None:
        pc2 = self.root / "synthetic.pc2"
        recovery.write_pc2(pc2, self.frames, 1, (0.0, 0.0, 0.2))
        for index in range(len(self.frames)):
            local = recovery.read_pc2_frame(pc2, index)
            world = local + np.asarray((0.0, 0.0, 0.2), dtype=np.float32)
            np.testing.assert_array_equal(world, self.frames[index])

    def test_positive_plain_grid_topology_and_uvs(self) -> None:
        faces = [[0, 2, 3, 1]]
        sidecar = {"vertices": 4, "first_frame": 1, "dtype": "float32", "layout": "frame-major xyz", "faces": faces}
        topology = recovery.validate_topology(sidecar, track_m=1.0, drop_m=1.0, fullness=1.0, quads_per_bolt=1)
        self.assertEqual((topology["cols"], topology["rows"]), (1, 1))
        np.testing.assert_array_equal(recovery.uv_per_loop(faces, 1, 1), [[0, 1], [0, 0], [1, 0], [1, 1]])

    def test_positive_stream_validation_counts_changing_frames(self) -> None:
        mapped = recovery.open_stream(self.stream, 3, 4)
        result = recovery.validate_stream(mapped)
        self.assertEqual(result["frames_nonzero"], 3)
        self.assertEqual(result["frames_changing"], 3)

    def test_negative_wrong_byte_count_is_refused(self) -> None:
        with self.assertRaisesRegex(recovery.RecoveryError, "stream byte size"):
            recovery.open_stream(self.stream, 4, 4)

    def test_negative_changed_face_order_is_refused(self) -> None:
        sidecar = {
            "vertices": 4,
            "first_frame": 1,
            "dtype": "float32",
            "layout": "frame-major xyz",
            "faces": [[0, 1, 3, 2]],
        }
        with self.assertRaisesRegex(recovery.RecoveryError, "topology"):
            recovery.validate_topology(sidecar, track_m=1.0, drop_m=1.0, fullness=1.0, quads_per_bolt=1)

    def test_negative_unchanged_frame_is_refused(self) -> None:
        bad = np.asarray([self.frames[0], self.frames[0]], dtype="<f4")
        with self.assertRaisesRegex(recovery.RecoveryError, "unchanged"):
            recovery.validate_stream(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
