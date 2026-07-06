import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES = ROOT / "scripts" / "generate_release_notes.py"
AGENT_HELP_CONTRACT = ROOT / "scripts" / "verify_agent_help_contract.py"
AGENT_EXAMPLES = ROOT / "scripts" / "verify_agent_examples.py"
CRD_COMPATIBILITY = ROOT / "scripts" / "verify_crd_compatibility.py"
CRD_UPGRADE_FIXTURES = ROOT / "scripts" / "verify_crd_upgrade_fixtures.py"
CRD_EXPLAIN_QUALITY = ROOT / "scripts" / "verify_crd_explain_quality.py"
CONFORMANCE_SUITE = ROOT / "scripts" / "verify_conformance_suite.py"
CONTROLLER_CONTRACT = ROOT / "scripts" / "verify_controller_contract.py"
CONTROLLER_RBAC = ROOT / "scripts" / "verify_controller_rbac.py"
CONTROLLER_RUNTIME = ROOT / "scripts" / "verify_controller_runtime_contract.py"
CONTROLLER_DEPLOYMENT = ROOT / "scripts" / "verify_controller_deployment.py"
CONTROLLER_RESOURCE_BUDGET = ROOT / "scripts" / "verify_controller_resource_budget.py"
LIGHTWEIGHT_CLUSTER_SMOKE = ROOT / "scripts" / "verify_lightweight_cluster_smoke.py"
HELM_CHART = ROOT / "scripts" / "verify_helm_chart.py"
KUSTOMIZE = ROOT / "scripts" / "verify_kustomize.py"
RELEASE_ARCHIVES = ROOT / "scripts" / "verify_release_archives.py"
KREW_MANIFEST = ROOT / "scripts" / "verify_krew_manifest.py"
SUPPLY_CHAIN = ROOT / "scripts" / "verify_supply_chain.py"
SECURITY_DOCS = ROOT / "scripts" / "verify_security_docs.py"
API_FREEZE = ROOT / "scripts" / "verify_api_freeze.py"
DOCS_FREEZE = ROOT / "scripts" / "verify_docs_freeze.py"
LIVE_VALIDATION_READINESS = ROOT / "scripts" / "verify_live_validation_readiness.py"
PROJECT_GOVERNANCE = ROOT / "scripts" / "verify_project_governance.py"
AIRGAP_BUNDLE = ROOT / "scripts" / "verify_airgap_bundle.py"
KYVERNO_ADAPTER = ROOT / "scripts" / "verify_kyverno_adapter.py"
OPA_ADAPTER = ROOT / "scripts" / "verify_opa_adapter.py"
KUBE_LINTER_ADAPTER = ROOT / "scripts" / "verify_kube_linter_adapter.py"
KUBE_SCORE_ADAPTER = ROOT / "scripts" / "verify_kube_score_adapter.py"
PLUTO_ADAPTER = ROOT / "scripts" / "verify_pluto_adapter.py"
ADAPTER_CONTRACT = ROOT / "scripts" / "verify_adapter_contract.py"
MCP_CONTRACT = ROOT / "scripts" / "verify_mcp_contract.py"
EXECUTE_DISABLED = ROOT / "scripts" / "verify_execute_disabled.py"
ADMISSION_WEBHOOK = ROOT / "scripts" / "verify_admission_webhook.py"
ADMISSION_POLICY = ROOT / "scripts" / "verify_admission_policy.py"
ADMISSION_DIGEST_GATE = ROOT / "scripts" / "verify_admission_digest_gate.py"
ADMISSION_AUDIT = ROOT / "scripts" / "verify_admission_audit.py"


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

    def test_verify_agent_help_contract(self):
        result = subprocess.run(
            [sys.executable, str(AGENT_HELP_CONTRACT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-help-contract: passed", result.stdout)
        self.assertIn("schemaVersion: kube-actuary.help.v1", result.stdout)

    def test_verify_agent_examples(self):
        result = subprocess.run(
            [sys.executable, str(AGENT_EXAMPLES)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-examples: passed", result.stdout)
        self.assertIn("writes: disabled", result.stdout)

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

    def test_verify_conformance_suite(self):
        result = subprocess.run(
            [sys.executable, str(CONFORMANCE_SUITE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("conformance-suite: passed", result.stdout)
        self.assertIn("upstream-minors: 1.36, 1.35, 1.34", result.stdout)

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

    def test_verify_controller_deployment(self):
        result = subprocess.run(
            [sys.executable, str(CONTROLLER_DEPLOYMENT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("controller-deployment: passed", result.stdout)
        self.assertIn("runtime: serve", result.stdout)

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

    def test_verify_security_docs(self):
        result = subprocess.run(
            [sys.executable, str(SECURITY_DOCS)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("security-docs: passed", result.stdout)
        self.assertIn("threat-model: present", result.stdout)

    def test_verify_api_freeze(self):
        result = subprocess.run(
            [sys.executable, str(API_FREEZE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("api-freeze: passed", result.stdout)
        self.assertIn("breaking-schema-diff: guarded", result.stdout)

    def test_verify_docs_freeze(self):
        result = subprocess.run(
            [sys.executable, str(DOCS_FREEZE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs-freeze: passed", result.stdout)
        self.assertIn("public-examples: 10 checked", result.stdout)

    def test_verify_live_validation_readiness(self):
        result = subprocess.run(
            [sys.executable, str(LIVE_VALIDATION_READINESS)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("live-validation-readiness: passed", result.stdout)
        self.assertIn("mode: inventory-only", result.stdout)
        self.assertIn("cluster-writes: disabled", result.stdout)

    def test_verify_project_governance(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_GOVERNANCE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("project-governance: passed", result.stdout)
        self.assertIn("contributing: present", result.stdout)

    def test_verify_airgap_bundle(self):
        result = subprocess.run(
            [sys.executable, str(AIRGAP_BUNDLE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("airgap-bundle: passed", result.stdout)
        self.assertIn("offline-checklist: present", result.stdout)

    def test_verify_kyverno_adapter(self):
        result = subprocess.run(
            [sys.executable, str(KYVERNO_ADAPTER)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kyverno-adapter: passed", result.stdout)
        self.assertIn("fail-fixture: policy-fail", result.stdout)

    def test_verify_opa_adapter(self):
        result = subprocess.run(
            [sys.executable, str(OPA_ADAPTER)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("opa-adapter: passed", result.stdout)
        self.assertIn("fail-fixture: policy-fail", result.stdout)

    def test_verify_kube_linter_adapter(self):
        result = subprocess.run(
            [sys.executable, str(KUBE_LINTER_ADAPTER)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kube-linter-adapter: passed", result.stdout)
        self.assertIn("fail-fixture: policy-fail", result.stdout)

    def test_verify_kube_score_adapter(self):
        result = subprocess.run(
            [sys.executable, str(KUBE_SCORE_ADAPTER)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kube-score-adapter: passed", result.stdout)
        self.assertIn("fail-fixture: policy-fail", result.stdout)

    def test_verify_pluto_adapter(self):
        result = subprocess.run(
            [sys.executable, str(PLUTO_ADAPTER)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pluto-adapter: passed", result.stdout)
        self.assertIn("fail-fixture: deprecated-api-found", result.stdout)

    def test_verify_adapter_contract(self):
        result = subprocess.run(
            [sys.executable, str(ADAPTER_CONTRACT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("adapter-contract: passed", result.stdout)
        self.assertIn("severity: normalized", result.stdout)

    def test_verify_mcp_contract(self):
        result = subprocess.run(
            [sys.executable, str(MCP_CONTRACT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mcp-contract: passed", result.stdout)
        self.assertIn("execute-tool: disabled", result.stdout)

    def test_verify_execute_disabled(self):
        result = subprocess.run(
            [sys.executable, str(EXECUTE_DISABLED)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("execute-disabled: passed", result.stdout)
        self.assertIn("mcp-execute: disabled", result.stdout)

    def test_verify_admission_webhook(self):
        result = subprocess.run(
            [sys.executable, str(ADMISSION_WEBHOOK)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("admission-webhook: passed", result.stdout)
        self.assertIn("failurePolicy: Ignore", result.stdout)

    def test_verify_admission_policy(self):
        result = subprocess.run(
            [sys.executable, str(ADMISSION_POLICY)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("admission-policy: passed", result.stdout)
        self.assertIn("deny-fixtures: 2", result.stdout)

    def test_verify_admission_digest_gate(self):
        result = subprocess.run(
            [sys.executable, str(ADMISSION_DIGEST_GATE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("admission-digest-gate: passed", result.stdout)
        self.assertIn("tamper-fixtures: 2", result.stdout)

    def test_verify_admission_audit(self):
        result = subprocess.run(
            [sys.executable, str(ADMISSION_AUDIT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("admission-audit: passed", result.stdout)
        self.assertIn("runbook: present", result.stdout)


if __name__ == "__main__":
    unittest.main()
