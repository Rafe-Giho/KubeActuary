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
CONTROLLER_RUNTIME = ROOT / "scripts" / "verify_controller_runtime_contract.py"
CONTROLLER_RESOURCE_BUDGET = ROOT / "scripts" / "verify_controller_resource_budget.py"
LIGHTWEIGHT_CLUSTER_SMOKE = ROOT / "scripts" / "verify_lightweight_cluster_smoke.py"
HELM_CHART = ROOT / "scripts" / "verify_helm_chart.py"
KUSTOMIZE = ROOT / "scripts" / "verify_kustomize.py"
RELEASE_ARCHIVES = ROOT / "scripts" / "verify_release_archives.py"
KREW_MANIFEST = ROOT / "scripts" / "verify_krew_manifest.py"
SUPPLY_CHAIN = ROOT / "scripts" / "verify_supply_chain.py"


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

    def test_verify_controller_runtime_contract(self):
        result = subprocess.run(
            [sys.executable, str(CONTROLLER_RUNTIME)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("controller-runtime: passed", result.stdout)
        self.assertIn("metrics: prometheus-text", result.stdout)
        self.assertIn("leader-election: leases.coordination.k8s.io", result.stdout)

    def test_verify_controller_resource_budget(self):
        result = subprocess.run(
            [sys.executable, str(CONTROLLER_RESOURCE_BUDGET)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("controller-resource-budget: passed", result.stdout)
        self.assertIn("idle-cpu-budget: <50m", result.stdout)
        self.assertIn("idle-memory-budget: <64Mi", result.stdout)

    def test_verify_lightweight_cluster_smoke(self):
        result = subprocess.run(
            [sys.executable, str(LIGHTWEIGHT_CLUSTER_SMOKE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("lightweight-cluster-smoke: passed", result.stdout)
        self.assertIn("providers: kind, minikube, microk8s, k3s", result.stdout)

    def test_verify_helm_chart(self):
        result = subprocess.run(
            [sys.executable, str(HELM_CHART)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("helm-chart: passed", result.stdout)
        self.assertIn("crd: included", result.stdout)
        self.assertIn("controller: optional", result.stdout)

    def test_verify_kustomize(self):
        result = subprocess.run(
            [sys.executable, str(KUSTOMIZE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kustomize: passed", result.stdout)
        self.assertIn("overlay: controller-namespace", result.stdout)
        self.assertIn("overlay: controller-cluster", result.stdout)

    def test_verify_release_archives(self):
        result = subprocess.run(
            [sys.executable, str(RELEASE_ARCHIVES)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("release-archives: passed", result.stdout)
        self.assertIn("sha256: verified", result.stdout)
        self.assertIn("install-smoke: passed", result.stdout)

    def test_verify_krew_manifest(self):
        result = subprocess.run(
            [sys.executable, str(KREW_MANIFEST)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("krew-manifest: passed", result.stdout)
        self.assertIn("plugin: actuary", result.stdout)

    def test_verify_supply_chain(self):
        result = subprocess.run(
            [sys.executable, str(SUPPLY_CHAIN)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("supply-chain: passed", result.stdout)
        self.assertIn("archive-digests: verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
