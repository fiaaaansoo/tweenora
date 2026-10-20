import sys
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import render


class CommandTest(unittest.TestCase):
    def test_minimal_command(self):
        cmd = render.build_command(Path("g.exe"), Path("a/b.riv"), Path("out"))
        self.assertEqual(
            cmd,
            ["g.exe", "-b", "gl", "-d", "-s", str(Path("a/b.riv")), "-o", str(Path("out"))],
        )

    def test_artboard_and_state_machine(self):
        cmd = render.build_command(
            Path("g.exe"), Path("a.riv"), Path("o"), artboard="Main", state_machine="SM"
        )
        self.assertIn("-t", cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], "Main")
        self.assertEqual(cmd[cmd.index("-S") + 1], "SM")

    def test_backend_is_gl_by_default_and_overridable(self):
        self.assertEqual(render.build_command(Path("g"), Path("a"), Path("o"))[1:3], ["-b", "gl"])
        self.assertEqual(
            render.build_command(Path("g"), Path("a"), Path("o"), backend="d3d")[1:3],
            ["-b", "d3d"],
        )

    def test_environment_fixes_the_advance(self):
        env = render.build_env({"PATH": "x"}, advance=12)
        self.assertEqual(env["RIVE_GOLDENS_ADVANCE"], "12")
        self.assertEqual(env["PATH"], "x")

    def test_environment_drops_inherited_advance(self):
        env = render.build_env({"RIVE_GOLDENS_ADVANCE": "99"}, advance=0)
        self.assertEqual(env["RIVE_GOLDENS_ADVANCE"], "0")

    def test_output_name_is_the_stem(self):
        self.assertEqual(render.output_png(Path("o"), Path("x/y/scene.riv")), Path("o") / "scene.png")
        self.assertEqual(render.output_png(Path("o"), Path("scene.twno")), Path("o") / "scene.png")

    def test_negative_advance_is_rejected(self):
        with self.assertRaises(ValueError):
            render.build_env({}, advance=-1)


if __name__ == "__main__":
    unittest.main()
