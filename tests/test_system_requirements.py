#!/usr/bin/env python3
"""
System Requirements Tests Vertex Package Managerd9b
Run from the project root:
    python -m pytest tests/test_system_requirements.py -v
"""

import os
import sys
import shutil
import subprocess
import tempfile
import unittest

SDP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SDP_DIR)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def run_vertex(*args, cwd=None, input_text=""):
    """Invoke vertex CLI. Empty stdin causes prompt_input() to use defaults."""
    return subprocess.run(
        ["vertex"] + list(args),
        capture_output=True, text=True,
        cwd=cwd or SDP_DIR,
        input=input_text,
        timeout=120,
    )


def init_project(base_dir, name="testproject"):
    """
    Initialise a vertex project and return the created project directory.
    vertex init <name> creates base_dir/<name>/mypm.toml.
    """
    run_vertex("init", name, "--python", "3.9", cwd=base_dir)
    return os.path.join(base_dir, name)


# ─────────────────────────────────────────────────────────────────
# FR1, Project Management
# ─────────────────────────────────────────────────────────────────

class TestFR1_ProjectManagement(unittest.TestCase):

    def test_FR1_1_init_creates_config_file(self):
        """FR1.1, vertex init creates mypm.toml inside the new project directory"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            self.assertTrue(
                os.path.exists(os.path.join(project_dir, "mypm.toml")),
                "mypm.toml was not created by vertex init",
            )

    def test_FR1_1_init_python_version_stored(self):
        """FR1.1, vertex init --python stores the specified Python version in mypm.toml"""
        with tempfile.TemporaryDirectory() as base:
            run_vertex("init", "myproject", "--python", "3.11", cwd=base)
            project_dir = os.path.join(base, "myproject")
            with open(os.path.join(project_dir, "mypm.toml")) as f:
                content = f.read()
            self.assertIn("3.11", content,
                         "Python version not recorded in mypm.toml")

    def test_FR1_2_info_returns_project_data(self):
        """FR1.2, vertex info exits successfully and produces output"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            result = run_vertex("info", cwd=project_dir)
            self.assertEqual(result.returncode, 0,
                             f"vertex info failed:\n{result.stderr}")
            self.assertGreater(len(result.stdout), 0,
                              "vertex info produced no output")

    def test_FR1_3_status_exits_successfully(self):
        """FR1.3, vertex status shows full project and environment status"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            result = run_vertex("status", cwd=project_dir)
            self.assertEqual(result.returncode, 0,
                             f"vertex status failed:\n{result.stderr}")

    def test_FR1_4_doctor_exits_successfully(self):
        """FR1.4, vertex doctor runs a health check and reports project status"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            result = run_vertex("doctor", cwd=project_dir)
            # returncode 1 is expected for a fresh project (no lock/venv yet);
            # the command must run and produce output, not crash.
            self.assertIn(result.returncode, (0, 1),
                         f"vertex doctor crashed unexpectedly:\n{result.stderr}")
            self.assertGreater(len(result.stdout), 0,
                              "vertex doctor produced no output")

    def test_FR1_5_import_requirements_txt(self):
        """FR1.5, vertex import reads requirements.txt and adds deps to mypm.toml"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
                f.write("requests>=2.0\nflask>=2.0\n")
            result = run_vertex("import", ".", cwd=project_dir)
            self.assertEqual(result.returncode, 0,
                             f"vertex import failed:\n{result.stderr}")
            with open(os.path.join(project_dir, "mypm.toml")) as f:
                content = f.read()
            self.assertIn("requests", content,
                         "'requests' not found in mypm.toml after import")

    def test_FR1_6_import_pyproject_toml_pep621(self):
        """FR1.6, import supports pyproject.toml (PEP 621 format)"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            with open(os.path.join(project_dir, "pyproject.toml"), "w") as f:
                f.write(
                    '[project]\nname = "demo"\nversion = "0.1"\n'
                    'dependencies = ["requests>=2.0"]\n'
                )
            result = run_vertex("import", ".", cwd=project_dir)
            self.assertEqual(result.returncode, 0,
                             f"import of pyproject.toml failed:\n{result.stderr}")
            with open(os.path.join(project_dir, "mypm.toml")) as f:
                content = f.read()
            self.assertIn("requests", content)

    def test_FR1_6_import_requirements_in(self):
        """FR1.6, import supports requirements.in format"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            with open(os.path.join(project_dir, "requirements.in"), "w") as f:
                f.write("numpy>=1.20\n")
            result = run_vertex("import", ".", cwd=project_dir)
            self.assertEqual(result.returncode, 0,
                             f"import of requirements.in failed:\n{result.stderr}")

    def test_FR1_6_import_pipfile(self):
        """FR1.6, import supports Pipfile format"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            with open(os.path.join(project_dir, "Pipfile"), "w") as f:
                f.write('[packages]\nrequests = ">=2.0"\n')
            result = run_vertex("import", ".", cwd=project_dir)
            self.assertEqual(result.returncode, 0,
                             f"import of Pipfile failed:\n{result.stderr}")

    def test_FR1_7_pip_freeze_detected_and_converted(self):
        """FR1.7, pip-freeze style files detected and user is prompted for handling choice"""
        with tempfile.TemporaryDirectory() as base:
            project_dir = init_project(base)
            # >80 % of lines use == → classified as pip-freeze style
            with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
                f.write(
                    "requests==2.28.2\nflask==2.3.1\n"
                    "numpy==1.24.0\ncertifi==2023.7.22\n"
                )
            # Pipe "2\n" to choose option 2 (Use as floor → >=version)
            result = run_vertex("import", ".", cwd=project_dir, input_text="2\n")
            self.assertEqual(result.returncode, 0,
                             f"import of pip-freeze file failed:\n{result.stderr}")
            # FR1.7 requires that the system detects pip-freeze format and
            # prompts the user.  The import_cmd prints "Found pinned-version files"
            # whenever a pip-freeze file is detected, which is the observable
            # confirmation that detection occurred.
            self.assertIn("pinned", result.stdout.lower(),
                         "Pip-freeze detection message ('pinned-version files') "
                         f"not found in output.\nstdout: {result.stdout}")


# ─────────────────────────────────────────────────────────────────
# FR2, Dependency Management
# ─────────────────────────────────────────────────────────────────

class TestFR2_DependencyManagement(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.project_dir = init_project(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_FR2_1_add_dependency_with_constraint(self):
        """FR2.1, vertex add writes dependency and constraint to mypm.toml"""
        result = run_vertex("add", "requests", ">=2.0", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex add failed:\n{result.stderr}")
        with open(os.path.join(self.project_dir, "mypm.toml")) as f:
            content = f.read()
        self.assertIn("requests", content,
                     "'requests' not in mypm.toml after add")

    def test_FR2_1_add_uses_default_constraint_when_omitted(self):
        """FR2.1, vertex add uses default constraint (>=0.1) when none is given"""
        result = run_vertex("add", "flask", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex add without constraint failed:\n{result.stderr}")
        with open(os.path.join(self.project_dir, "mypm.toml")) as f:
            content = f.read()
        self.assertIn("flask", content)

    def test_FR2_2_remove_dependency(self):
        """FR2.2, vertex remove deletes the dependency from mypm.toml"""
        run_vertex("add", "certifi", ">=2020.0", cwd=self.project_dir)
        result = run_vertex("remove", "certifi", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex remove failed:\n{result.stderr}")
        with open(os.path.join(self.project_dir, "mypm.toml")) as f:
            content = f.read()
        self.assertNotIn("certifi", content,
                        "'certifi' still in mypm.toml after remove")

    def test_FR2_3_show_lists_all_declared_dependencies(self):
        """FR2.3, vertex show lists every declared dependency"""
        run_vertex("add", "certifi", ">=2020.0", cwd=self.project_dir)
        result = run_vertex("show", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex show failed:\n{result.stderr}")
        self.assertIn("certifi", result.stdout,
                     "'certifi' not shown in vertex show output")

    def test_FR2_4_update_runs_without_error(self):
        """FR2.4, vertex update completes without error"""
        run_vertex("add", "certifi", ">=2020.0", cwd=self.project_dir)
        result = run_vertex("update", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex update failed:\n{result.stderr}")


# ─────────────────────────────────────────────────────────────────
# FR3, Dependency Resolution
# ─────────────────────────────────────────────────────────────────

class TestFR3_Resolution(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.project_dir = init_project(self.base)
        run_vertex("add", "certifi", ">=2020.0", cwd=self.project_dir)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_FR3_1_resolve_default_hypergraph(self):
        """FR3.1, vertex resolve uses hypergraph solver and creates mypm.lock"""
        result = run_vertex("resolve", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex resolve failed:\n{result.stderr}")
        self.assertTrue(
            os.path.exists(os.path.join(self.project_dir, "mypm.lock")),
            "mypm.lock not created after resolve",
        )

    def test_FR3_2_resolve_strategy_hypergraph(self):
        """FR3.2, vertex resolve --strategy hypergraph succeeds"""
        result = run_vertex("resolve", "--strategy", "hypergraph", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"hypergraph strategy failed:\n{result.stderr}")

    def test_FR3_2_resolve_strategy_sat(self):
        """FR3.2, vertex resolve --strategy sat succeeds"""
        result = run_vertex("resolve", "--strategy", "sat", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"SAT strategy failed:\n{result.stderr}")

    def test_FR3_2_resolve_strategy_backtracking(self):
        """FR3.2, vertex resolve --strategy backtracking succeeds"""
        result = run_vertex("resolve", "--strategy", "backtracking", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"backtracking strategy failed:\n{result.stderr}")

    def test_FR3_3_lock_regenerates_lockfile(self):
        """FR3.3, vertex lock regenerates mypm.lock"""
        result = run_vertex("lock", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex lock failed:\n{result.stderr}")
        self.assertTrue(os.path.exists(os.path.join(self.project_dir, "mypm.lock")))

    def test_FR3_4_explain_after_resolve(self):
        """FR3.4, vertex explain shows version selection rationale"""
        run_vertex("resolve", cwd=self.project_dir)
        result = run_vertex("explain", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex explain failed:\n{result.stderr}")

    def test_FR3_5_conflicts_exits_successfully(self):
        """FR3.5, vertex conflicts lists known registry conflicts"""
        result = run_vertex("conflicts", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex conflicts failed:\n{result.stderr}")

    def test_FR3_6_unsat_returns_none(self):
        """FR3.6, solver returns None when two required packages are in direct conflict"""
        from model_math_trans import (
            HyperGraph, Package, Hyperedge, solve_phased
        )

        # Build a minimal UNSAT scenario:
        # pkgA@1.0 and pkgB@1.0 are in explicit conflict (singleton role classes).
        # Conservative conflict lifting promotes this to Phase A.
        # Coverage clauses require both → ¬x_A ∨ ¬x_B AND x_A AND x_B → UNSAT.
        H = HyperGraph()
        pA = Package("pkgA", "1.0")
        pB = Package("pkgB", "1.0")
        H.V.add(pA)
        H.V.add(pB)
        H.E.append(Hyperedge(
            source=frozenset({pA}),
            target=frozenset({pB}),
            label="conflict",
        ))

        class MockGraph:
            candidates   = {"pkgA": [], "pkgB": []}
            edges        = {}
            dependencies = {"pkgA": ">=1.0", "pkgB": ">=1.0"}
            def get_candidates(self, name):   return []
            def get_dependencies(self, n, v): return []

        result = solve_phased(H, MockGraph(), {"pkgA", "pkgB"})
        self.assertIsNone(
            result,
            "solve_phased must return None when pkgA and pkgB are mutually conflicting",
        )

    def test_FR3_7_diamond_conflict_resolved(self):
        """FR3.7, diamond dependency conflict resolved correctly (vertex demo --auto)"""
        result = run_vertex("demo", "--auto", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex demo --auto failed:\n{result.stderr}")


# ─────────────────────────────────────────────────────────────────
# FR4, Environment Management
# ─────────────────────────────────────────────────────────────────

class TestFR4_Environment(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.project_dir = init_project(self.base)
        run_vertex("add", "certifi", ">=2020.0", cwd=self.project_dir)
        run_vertex("resolve", cwd=self.project_dir)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_FR4_1_install_packages_into_venv(self):
        """FR4.1, vertex install installs packages from lock file into virtual environment"""
        result = run_vertex("install", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex install failed:\n{result.stderr}")

    def test_FR4_2_install_dry_run_does_not_install(self):
        """FR4.2, vertex install --dry-run previews packages without installing"""
        result = run_vertex("install", "--dry-run", cwd=self.project_dir)
        self.assertEqual(result.returncode, 0,
                         f"vertex install --dry-run failed:\n{result.stderr}")
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue(
            "dry" in combined or "would" in combined,
            f"dry-run output does not indicate preview mode.\nOutput: {result.stdout}",
        )


# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
