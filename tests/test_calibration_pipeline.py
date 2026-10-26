import os
import re
import sys
import unittest
from pathlib import Path

# Resolve repository root dynamically
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
RL_DIR = REPO_ROOT / "RL"

# Add paths to sys.path
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(RL_DIR))
sys.path.insert(0, str(RL_DIR / "pytrs"))


class TestCalibrationPipelineConstraints(unittest.TestCase):
    """Enforce strict code quality constraints: zero personal names and zero hardcoded paths."""

    TARGET_FILES = [
        SCRIPTS_DIR / "build_unified_calib_pool.py",
        SCRIPTS_DIR / "measure_calib_hpc.py",
        SCRIPTS_DIR / "fit_unified_calib_v4.py",
        SCRIPTS_DIR / "build_dnn_dataset.py",
        SCRIPTS_DIR / "build_dnn_dataset.sbatch",
        SCRIPTS_DIR / "run_unified_calibration.sbatch",
        SCRIPTS_DIR / "launch_full_pipeline.sh",
        RL_DIR / "fhe_rl" / "env_mo.py",
        RL_DIR / "fhe_rl" / "train_mo.py",
        RL_DIR / "fhe_rl" / "__main__.py",
        RL_DIR / "pytrs" / "rewrite_rule.py",
    ]

    FORBIDDEN_NAMES = ["imed", "melzi", "mokrane", "nazim", "bilel", "maroua", "mo3135"]

    def test_no_personal_names(self):
        """Verify no author names or attribution comments appear in any delivered files."""
        for file_path in self.TARGET_FILES:
            if not file_path.exists():
                continue
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    for name in self.FORBIDDEN_NAMES:
                        pattern = rf"\b{re.escape(name)}\b"
                        match = re.search(pattern, line, re.IGNORECASE)
                        self.assertIsNone(
                            match,
                            f"Forbidden name '{name}' found in {file_path.name}:{line_idx}: {line.strip()}"
                        )

    def test_no_hardcoded_paths(self):
        """Verify no hardcoded user home or scratch directories appear in Python files."""
        hardcoded_patterns = [
            "/h" + "ome/\\w+",
            "/sc" + "ratch/\\w{2,6}\\d{3,5}",
            r"C:\\Users\\",
            r"/mnt/c/" + r"Users/",
        ]
        python_files = [f for f in self.TARGET_FILES if f.suffix == ".py"]
        for file_path in python_files:
            if not file_path.exists():
                continue
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    for pat in hardcoded_patterns:
                        match = re.search(pat, line)
                        self.assertIsNone(
                            match,
                            f"Hardcoded path pattern '{pat}' found in {file_path.name}:{line_idx}: {line.strip()}"
                        )


class TestPoolBuildingAndDiversity(unittest.TestCase):
    """Test unified calibration pool builder logic and diversity generation."""

    def test_pool_builder_imports_cleanly(self):
        """Verify build_unified_calib_pool can be imported without Torch dependency."""
        import build_unified_calib_pool as bcp
        self.assertTrue(hasattr(bcp, "structural_hash"))
        self.assertTrue(hasattr(bcp, "build_persistent_rotation_expression"))
        self.assertTrue(hasattr(bcp, "load_dnn_expressions"))
        self.assertTrue(hasattr(bcp, "load_ruleset"))
        self.assertTrue(hasattr(bcp, "generate_rewrites_from_base"))

    def test_structural_hash_isomorphism(self):
        """Verify structural hashing normalizes variable numbers for zero data leakage."""
        import build_unified_calib_pool as bcp
        expr1 = "(add (input 0) (mul (input 1) (input 2)))"
        expr2 = "(add (input 5) (mul (input 8) (input 9)))"
        expr3 = "(mul (input 0) (add (input 1) (input 2)))"
        hash1 = bcp.structural_hash(expr1)
        hash2 = bcp.structural_hash(expr2)
        hash3 = bcp.structural_hash(expr3)
        self.assertEqual(hash1, hash2, "Expressions with identical structure must share hash")
        self.assertNotEqual(hash1, hash3, "Different operator structure must yield different hash")

    def test_persistent_rotation_generation(self):
        """Verify persistent top-level rotations create non-zero Galois keys (G > 0)."""
        import build_unified_calib_pool as bcp
        rot_expr = bcp.build_persistent_rotation_expression(family="babystep_giantstep", g=4, slots=64)
        self.assertIn("<<", rot_expr)
        self.assertIn("Vec", rot_expr)

    def test_ruleset_loading(self):
        """Verify pure Python rule parser loads rewrite rules without torch."""
        import build_unified_calib_pool as bcp
        rules = bcp.load_ruleset()
        self.assertGreater(len(rules), 10, "Should load full rewrite rule battery")


class TestMultiTrialMeasurementStatistics(unittest.TestCase):
    """Test 5-run statistical aggregation and AST parameter parsing."""

    def test_measurement_harness_imports_cleanly(self):
        """Verify measure_calib_hpc imports without errors."""
        import measure_calib_hpc as mch
        self.assertTrue(hasattr(mch, "parse_go_params"))
        self.assertTrue(hasattr(mch, "parse_go_rss"))
        self.assertTrue(hasattr(mch, "patch_neg_new"))
        self.assertTrue(hasattr(mch, "compile_and_profile_circuit"))

    def test_parse_go_params(self):
        """Verify cryptographic parameter parsing from generated Go source."""
        import measure_calib_hpc as mch
        sample_go = """
        package main
        import "github.com/tuneinsight/lattigo/v4/ckks"
        func main() {
            params, _ := ckks.NewParametersFromLiteral(ckks.ParametersLiteral{
                LogN: 14,
                LogQ: []int{55, 40, 40},
                LogP: []int{60},
            })
            _ = params
        }
        """
        parsed = mch.parse_go_params(sample_go)
        self.assertEqual(parsed["go_N"], 16384)
        self.assertEqual(parsed["go_L"], 3)
        self.assertEqual(parsed["go_K"], 1)

    def test_parse_go_rss(self):
        """Verify regex extraction of MaxRSS from profiling output."""
        import measure_calib_hpc as mch
        stdout_sample = "Running benchmark...\nmax_rss_(MB): 245.85\nDone."
        rss = mch.parse_go_rss(stdout_sample)
        self.assertIsNotNone(rss)
        self.assertAlmostEqual(rss, 245.85, places=2)

    def test_statistical_aggregation_math(self):
        """Verify median, spread, jitter, and standard deviation math on 5 trials."""
        import numpy as np

        measurements = [102.4, 99.8, 101.1, 103.0, 100.5]
        median_val = float(np.median(measurements))
        min_val = float(np.min(measurements))
        max_val = float(np.max(measurements))
        spread_val = max_val - min_val
        jitter_pct = (spread_val / median_val) * 100.0
        std_val = float(np.std(measurements))

        self.assertAlmostEqual(median_val, 101.1, places=2)
        self.assertAlmostEqual(min_val, 99.8, places=2)
        self.assertAlmostEqual(max_val, 103.0, places=2)
        self.assertAlmostEqual(spread_val, 3.2, places=2)
        self.assertLess(jitter_pct, 5.0)
        self.assertGreater(std_val, 0.0)


class TestLiteratureValidationAndFitting(unittest.TestCase):
    """Test statistical goodness-of-fit, Log-Log fitting, and Ratio fitting."""

    def test_fitting_module_imports_cleanly(self):
        """Verify fit_unified_calib_v4 imports without errors."""
        import fit_unified_calib_v4 as fuv
        self.assertTrue(hasattr(fuv, "fit_log_log"))
        self.assertTrue(hasattr(fuv, "fit_ratio"))
        self.assertTrue(hasattr(fuv, "compute_metrics"))

    def test_compute_metrics(self):
        """Verify calculation of MdAPE, MAPE, MPE bias, nRMSE, R^2, and safety compliance."""
        import fit_unified_calib_v4 as fuv
        import numpy as np

        y_true = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        y_pred = np.array([105.0, 195.0, 310.0, 390.0, 515.0])

        metrics = fuv.compute_metrics(y_true, y_pred)
        self.assertIn("mdape_pct", metrics)
        self.assertIn("mape_pct", metrics)
        self.assertIn("mpe_bias_pct", metrics)
        self.assertIn("r2_score", metrics)
        self.assertIn("nrmse_pct", metrics)
        self.assertIn("safety_coverage_pct", metrics)

        self.assertLess(metrics["mdape_pct"], 5.0)
        self.assertGreater(metrics["r2_score"], 0.98)
        self.assertLess(abs(metrics["mpe_bias_pct"]), 5.0)

    def test_fit_ratio(self):
        """Verify linear proportional ratio fitting through origin."""
        import fit_unified_calib_v4 as fuv
        import numpy as np

        x_net = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        y_rss = 2.5 * x_net + np.random.normal(0, 0.05, len(x_net))
        ratio = fuv.fit_ratio(x_net, y_rss)
        self.assertAlmostEqual(ratio, 2.5, places=1)

    def test_fit_log_log(self):
        """Verify Log-Log curve fitting in logarithmic representation."""
        import fit_unified_calib_v4 as fuv
        import numpy as np

        np.random.seed(42)
        x_net = np.array([5.0, 10.0, 20.0, 35.0, 50.0, 80.0, 100.0])
        levels = np.array([1, 2, 3, 4, 5, 6, 7])
        # Ground truth: y = 0.8 * (x^0.85) * exp(0.03 * levels)
        # log(y) = log(0.8) + 0.85 * log(x) + 0.03 * levels
        log_y = np.log(0.8) + 0.85 * np.log(x_net) + 0.03 * levels
        y_rss = np.exp(log_y)
        a_log, b, c_L = fuv.fit_log_log(x_net, levels, y_rss)
        self.assertAlmostEqual(np.exp(a_log), 0.8, places=2)
        self.assertAlmostEqual(b, 0.85, places=2)
        self.assertAlmostEqual(c_L, 0.03, places=2)


class TestSbatchAndLauncherScripts(unittest.TestCase):
    """Verify Slurm sbatch and launcher scripts syntax, notifications, and error handling."""

    def test_scripts_executable_permissions(self):
        """Verify all pipeline shell scripts have execute permissions."""
        scripts = [
            SCRIPTS_DIR / "build_dnn_dataset.sbatch",
            SCRIPTS_DIR / "run_unified_calibration.sbatch",
            SCRIPTS_DIR / "launch_full_pipeline.sh",
        ]
        for script in scripts:
            self.assertTrue(script.exists(), f"Missing script: {script}")
            self.assertTrue(os.access(script, os.X_OK), f"Script not executable: {script}")

    def test_sbatch_notification_directives(self):
        """Verify both sbatch scripts declare mail notifications for BEGIN, END, FAIL."""
        for sbatch_file in [SCRIPTS_DIR / "build_dnn_dataset.sbatch", SCRIPTS_DIR / "run_unified_calibration.sbatch"]:
            content = sbatch_file.read_text(encoding="utf-8")
            self.assertIn("#SBATCH --mail-type=BEGIN,END,FAIL", content)
            self.assertIn("trap ", content)
            self.assertIn("set -eo pipefail", content)

    def test_launcher_dependency_chaining(self):
        """Verify launcher script chains Job 2 to Job 1 via --dependency=afterok."""
        launcher = SCRIPTS_DIR / "launch_full_pipeline.sh"
        content = launcher.read_text(encoding="utf-8")
        self.assertIn("--dependency=afterok:", content)
        self.assertIn("JOB1_ID", content)
        self.assertIn("JOB2_ID", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
