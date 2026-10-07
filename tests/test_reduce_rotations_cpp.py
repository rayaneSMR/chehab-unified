import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RL_DIR = ROOT / "RL"
BUILD_DIR = ROOT / "build"
if str(RL_DIR) not in sys.path:
    sys.path.append(str(RL_DIR))

from pytrs.peak_ram import reduce_rotation_keys_pass


class TestReduceRotationKeysCppDifferential(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUILD_DIR / "CMakeCache.txt").exists():
            subprocess.run(
                ["cmake", "-S", str(ROOT), "-B", str(BUILD_DIR)],
                cwd=ROOT,
                check=True,
            )
        subprocess.run(
            [
                "cmake",
                "--build",
                str(BUILD_DIR),
                "--target",
                "rotation_keys_reference",
                "-j2",
            ],
            cwd=ROOT,
            check=True,
        )
        cls.reference = BUILD_DIR / "rotation_keys_reference"

    def compare_with_cpp(self, steps_freq, threshold):
        args = [
            str(self.reference),
            str(threshold),
            *(f"{step}:{frequency}" for step, frequency in steps_freq.items()),
        ]
        cpp_result = subprocess.run(args, capture_output=True, text=True)
        try:
            python_steps = reduce_rotation_keys_pass(steps_freq, threshold)
        except RuntimeError:
            self.assertEqual(cpp_result.returncode, 3, cpp_result.stdout)
            self.assertIn("could not go lower", cpp_result.stdout)
            return

        self.assertEqual(cpp_result.returncode, 0, cpp_result.stderr)
        cpp_steps = {int(step) for step in cpp_result.stdout.split()}
        self.assertEqual(python_steps, cpp_steps)

    def test_real_cpp_pass_matches_python_on_rotation_step_sets(self):
        cases = [
            ({3: 1, 15: 1, 19: 1, 20: 1}, 3),
            ({-3: 10, 5: 5}, 2),
            ({2: 10, 4: 20}, 2),
            ({3: 10, 4: 20, 5: 5}, 2),
            ({7: 2, 11: 7, 12: 4, 19: 1, 32: 3}, 4),
        ]
        for steps_freq, threshold in cases:
            with self.subTest(steps_freq=steps_freq, threshold=threshold):
                self.compare_with_cpp(steps_freq, threshold)


if __name__ == "__main__":
    unittest.main()
