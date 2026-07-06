import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES = ROOT / "scripts" / "generate_release_notes.py"
CRD_COMPATIBILITY = ROOT / "scripts" / "verify_crd_compatibility.py"
CRD_UPGRADE_FIXTURES = ROOT / "scripts" / "verify_crd_upgrade_fixtures.py"
CRD_EXPLAIN_QUALITY = ROOT / "scripts" / "verify_crd_explain_quality.py"
CONTROLLER_CONTRACT = ROOT / "scripts" / "verify_controller_contract.py"
CONTROLLER_RBAC = ROOT / "scripts" / "verify_controller_rbac.py"


class ReleaseToolTests(unittest.TestCase):
    def run_notes(self, *args):
        return subprocess.run(
            [sys.executable, str(RELEASE_NOTES), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_generate_release_notes_dry_run(self):
        result = self.run_notes("--version", "0.2.0", "--date", "2026-07-06", "--output", "-")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# KubeActuary 0.2.0 Release Notes", result.stdout)
        self.assertIn("add `collect dry-run`", result.stdout)
        self.assertIn("## Verification", result.stdout)
        self.assertIn("scripts/verify_release.py --version 0.2.0", result.stdout)
        self.assertIn("## Rollback", result.stdout)

    def test_generate_release_notes_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "notes.md"
            result = self.run_notes("--version", "0.2.0", "--date", "2026-07-06", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertIn("Status: draft", output.read_text())

    def test_verify_crd_compatibility_smoke(self):
        result = subprocess.run(
            [sys.executable, str(CRD_COMPATIBILITY)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crd-compatibility: passed", result.stdout)
        self.assertIn("upstream-minors: 1.36, 1.35, 1.34", result.stdout)

    def test_verify_crd_upgrade_fixtures(self):
        result = subprocess.run(
            [sys.executable, str(CRD_UPGRADE_FIXTURES)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crd-upgrade-fixtures: passed", result.stdout)
        self.assertIn("operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml", result.stdout)

    def test_verify_crd_explain_quality(self):
        result = subprocess.run(
            [sys.executable, str(CRD_EXPLAIN_QUALITY)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crd-explain-quality: passed", result.stdout)
        self.assertIn("commands: 7", result.stdout)

    def test_verify_controller_contract(self):
        result = subprocess.run(
            [sys.executable, str(CONTROLLER_CONTRACT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("controller-contract: passed", result.stdout)
        self.assertIn("operationcapsules.ops.kubeactuary.dev", result.stdout)

    def test_verify_controller_rbac(self):
        result = subprocess.run(
            [sys.executable, str(CONTROLLER_RBAC)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("controller-rbac: passed", result.stdout)
        self.assertIn("namespace-mode: Role/RoleBinding", result.stdout)
        self.assertIn("cluster-mode: ClusterRole/ClusterRoleBinding", result.stdout)
        self.assertIn("status-write-only: operationcapsules/status", result.stdout)


if __name__ == "__main__":
    unittest.main()
