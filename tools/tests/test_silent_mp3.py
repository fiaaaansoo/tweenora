import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import silent_mp3

SCRIPT = TOOLS_DIR / "silent_mp3.py"
COMMITTED = REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets" / "audio" / "silence.mp3"
HEADER = bytes([0xFF, 0xFB, 0x90, 0xC0])


class BuildTest(unittest.TestCase):
    def test_every_frame_starts_with_the_same_header(self):
        data = silent_mp3.build(5)
        self.assertEqual(len(data), 5 * silent_mp3.FRAME_SIZE)
        for index in range(5):
            start = index * silent_mp3.FRAME_SIZE
            self.assertEqual(data[start : start + 4], HEADER)

    def test_frames_carry_no_audio_data(self):
        data = silent_mp3.build(3)
        for index in range(3):
            start = index * silent_mp3.FRAME_SIZE
            self.assertEqual(set(data[start + 4 : start + silent_mp3.FRAME_SIZE]), {0})

    def test_duration_matches_the_frame_count(self):
        self.assertAlmostEqual(silent_mp3.duration_seconds(38), 38 * 1152 / 44100)

    def test_rejects_a_non_positive_count(self):
        with self.assertRaises(ValueError):
            silent_mp3.build(0)

    def test_deterministic(self):
        self.assertEqual(silent_mp3.build(10), silent_mp3.build(10))


class CommittedFileTest(unittest.TestCase):
    def test_committed_asset_is_what_the_script_generates(self):
        self.assertEqual(COMMITTED.read_bytes(), silent_mp3.build(silent_mp3.DEFAULT_FRAMES))

    def test_command_line_writes_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.mp3"
            subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "-o", str(target)], check=True
            )
            self.assertEqual(target.read_bytes(), COMMITTED.read_bytes())


if __name__ == "__main__":
    unittest.main()
