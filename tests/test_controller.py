import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


class ControllerReconcileTests(unittest.TestCase):
    def run_controller(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(CONTROLLER), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def write_capsule(self, document):
        tmpdir = tempfile.TemporaryDirectory()
        path = Path(tmpdir.name) / "operationcapsule.json"
        path.write_text(json.dumps(document))
        return tmpdir, path

    def capsule(self, evidence, rollback=None):
        return {
            "apiVersion": "ops.kubeactuary.dev/v1alpha1",
            "kind": "OperationCapsule",
            "metadata": {"name": "demo", "namespace": "default"},
            "spec": {
                "intent": "apply demo",
                "actor": {"type": "ai-agent", "name": "codex"},
                "proposedAction": {"verb": "manifest", "namespace": "default"},
                "risk": {"level": "medium", "reasons": ["cluster state may be modified"]},
                "requiredEvidence": ["intent", "server-dry-run", "rollback"],
                "evidence": evidence,
                "rollback": rollback or {"required": True, "provided": True},
            },
        }

    def test_reconcile_opens_gate_when_required_evidence_passes(self):
        tmpdir, path = self.write_capsule(
            self.capsule(
                [
                    {"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"},
                    {"id": "server-dry-run", "ok": True, "summary": "ok", "actor": "ci", "attachedAt": "now"},
                    {"id": "rollback", "ok": True, "summary": "ok", "actor": "ci", "attachedAt": "now"},
                ]
            )
        )
        with tmpdir:
            result = self.run_controller("reconcile", str(path))

        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual(status["phase"], "GateOpen")
        self.assertEqual(status["gate"], "Open")
        self.assertEqual(status["missingEvidence"], [])
        self.assertEqual(status["failedEvidence"], [])
        self.assertTrue(status["digest"].startswith("sha256:"))
        gate = next(condition for condition in status["conditions"] if condition["type"] == "GateOpen")
        self.assertEqual(gate["status"], "True")

    def test_reconcile_blocks_failed_required_evidence(self):
        tmpdir, path = self.write_capsule(
            self.capsule(
                [
                    {"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"},
                    {"id": "server-dry-run", "ok": False, "summary": "failed", "actor": "ci", "attachedAt": "now"},
                ],
                rollback={"required": True, "provided": False},
            )
        )
        with tmpdir:
            result = self.run_controller("reconcile", str(path), "--format", "patch")

        self.assertEqual(result.returncode, 0, result.stderr)
        patch = json.loads(result.stdout)
        status = patch["status"]
        self.assertEqual(status["phase"], "Blocked")
        self.assertEqual(status["gate"], "Closed")
        self.assertEqual(status["missingEvidence"], ["rollback"])
        self.assertEqual(status["failedEvidence"], ["server-dry-run"])
        blocked = next(condition for condition in status["conditions"] if condition["type"] == "Blocked")
        rollback = next(condition for condition in status["conditions"] if condition["type"] == "RollbackReady")
        self.assertEqual(blocked["status"], "True")
        self.assertEqual(rollback["status"], "False")

    def test_watch_command_only_targets_operationcapsules(self):
        result = self.run_controller("watch-command")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "kubectl get operationcapsules.ops.kubeactuary.dev -o json --watch --all-namespaces",
        )
        for forbidden in ("pods", "deployments", "events", "nodes"):
            self.assertNotIn(forbidden, result.stdout)

    def test_watch_command_can_be_namespace_scoped(self):
        result = self.run_controller("watch-command", "--namespace", "platform")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "kubectl get operationcapsules.ops.kubeactuary.dev -o json --watch -n platform",
        )

    def test_health_payload_is_deterministic(self):
        result = self.run_controller("health", "--started-at", "100", "--now", "145")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["uptimeSeconds"], 45)
        self.assertEqual(payload["watchResource"], "operationcapsules.ops.kubeactuary.dev")

    def test_ready_payload_reports_runtime_boundaries(self):
        result = self.run_controller("ready", "--rbac-mode", "cluster")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIs(payload["ready"], True)
        self.assertEqual(payload["checks"]["rbacMode"], "cluster")
        self.assertIs(payload["checks"]["statusPatchOnly"], True)
        self.assertEqual(payload["checks"]["watchResource"], "operationcapsules.ops.kubeactuary.dev")

    def test_metrics_payload_is_prometheus_text(self):
        result = self.run_controller("metrics", "--reconcile-total", "3", "--reconcile-errors-total", "1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# TYPE kubeactuary_controller_reconcile_total counter", result.stdout)
        self.assertIn("kubeactuary_controller_reconcile_total 3", result.stdout)
        self.assertIn("kubeactuary_controller_reconcile_errors_total 1", result.stdout)
        self.assertIn('watch_resource="operationcapsules.ops.kubeactuary.dev"', result.stdout)
        self.assertIn("kubeactuary_controller_idle_cpu_budget_millicores 50", result.stdout)
        self.assertIn("kubeactuary_controller_idle_memory_budget_mebibytes 64", result.stdout)

    def test_leader_election_payload_uses_kubernetes_lease(self):
        result = self.run_controller("leader-election", "--identity", "unit-test")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["resource"], "leases.coordination.k8s.io")
        self.assertEqual(payload["namespace"], "kubeactuary-system")
        self.assertEqual(payload["leaseName"], "kubeactuary-controller")
        self.assertEqual(payload["identity"], "unit-test")

    def test_resource_budget_payload_sets_low_overhead_targets(self):
        result = self.run_controller("resource-budget")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["budget"]["idleCpuMillicoresLessThan"], 50)
        self.assertEqual(payload["budget"]["idleMemoryMiLessThan"], 64)
        self.assertEqual(payload["budget"]["requests"], {"cpu": "10m", "memory": "32Mi"})
        self.assertEqual(payload["budget"]["limits"], {"cpu": "50m", "memory": "64Mi"})

    def test_measure_command_targets_controller_pods_only(self):
        result = self.run_controller("measure-command")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "kubectl top pod -n kubeactuary-system -l "
            "app.kubernetes.io/name=kubeactuary,app.kubernetes.io/component=controller --containers",
        )

    def test_serve_print_config_has_no_cluster_access(self):
        result = self.run_controller("serve", "--print-config")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["clusterAccess"], "none")
        self.assertEqual(payload["watchResource"], "operationcapsules.ops.kubeactuary.dev")
        self.assertEqual(payload["paths"], ["/healthz", "/readyz", "/metrics"])

    def test_patch_plan_handles_operationcapsule_list_without_execution(self):
        tmpdir = tempfile.TemporaryDirectory()
        path = Path(tmpdir.name) / "operationcapsules.json"
        path.write_text(
            json.dumps(
                {
                    "items": [
                        self.capsule(
                            [{"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"}]
                        )
                    ]
                }
            )
        )
        with tmpdir:
            result = self.run_controller("patch-plan", str(path))

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["writeExecution"], "disabled")
        self.assertEqual(plan["count"], 1)
        patch = plan["patches"][0]
        self.assertEqual(set(patch["patch"]), {"status"})
        self.assertIn("--subresource", patch["command"])
        self.assertIn("status", patch["command"])
        self.assertNotIn("apply", patch["command"])

    def test_sync_reads_operationcapsules_and_emits_plan_without_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = {"items": [self.capsule([{"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"}])]}
            log_path = Path(tmpdir) / "kubectl-calls.json"
            kubectl = Path(tmpdir) / "kubectl"
            kubectl.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json",
                        "import sys",
                        "from pathlib import Path",
                        f"log_path = Path({str(log_path)!r})",
                        "calls = json.loads(log_path.read_text()) if log_path.exists() else []",
                        "calls.append(sys.argv[1:])",
                        "log_path.write_text(json.dumps(calls))",
                        f"payload = {json.dumps(payload)!r}",
                        "if sys.argv[1] == 'get':",
                        "    print(payload)",
                        "    raise SystemExit(0)",
                        "print('unexpected kubectl call', file=sys.stderr)",
                        "raise SystemExit(9)",
                    ]
                )
            )
            kubectl.chmod(0o755)

            result = self.run_controller("sync", "--kubectl", str(kubectl))
            namespaced = self.run_controller("sync", "--kubectl", str(kubectl), "--namespace", "team-a")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(namespaced.returncode, 0, namespaced.stderr)
            calls = json.loads(log_path.read_text())

        self.assertEqual(
            calls,
            [
                ["get", "operationcapsules.ops.kubeactuary.dev", "-o", "json", "--all-namespaces"],
                ["get", "operationcapsules.ops.kubeactuary.dev", "-o", "json", "-n", "team-a"],
            ],
        )
        for call in calls:
            for forbidden in ("patch", "apply", "delete"):
                self.assertNotIn(forbidden, call)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["readExecution"], "kubectl-get")
        self.assertEqual(plan["writeExecution"], "disabled")
        self.assertEqual(plan["count"], 1)
        self.assertEqual(set(plan["patches"][0]["patch"]), {"status"})
        self.assertIn("patch", plan["patches"][0]["command"])

    def test_apply_status_defaults_to_server_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "operationcapsule.json"
            path.write_text(json.dumps(self.capsule([{"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"}])))
            log_path = Path(tmpdir) / "kubectl-calls.json"
            kubectl = Path(tmpdir) / "kubectl"
            kubectl.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json",
                        "import sys",
                        "from pathlib import Path",
                        f"log_path = Path({str(log_path)!r})",
                        "calls = json.loads(log_path.read_text()) if log_path.exists() else []",
                        "calls.append(sys.argv[1:])",
                        "log_path.write_text(json.dumps(calls))",
                        "if sys.argv[1] == 'patch':",
                        "    print('status patch ok')",
                        "    raise SystemExit(0)",
                        "print('unexpected kubectl call', file=sys.stderr)",
                        "raise SystemExit(9)",
                    ]
                )
            )
            kubectl.chmod(0o755)

            dry_run = self.run_controller("apply-status", str(path), "--kubectl", str(kubectl))
            execute = self.run_controller("apply-status", str(path), "--kubectl", str(kubectl), "--execute")
            calls = json.loads(log_path.read_text())

        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertEqual(execute.returncode, 0, execute.stderr)
        self.assertIn("--dry-run=server", calls[0])
        self.assertNotIn("--dry-run=server", calls[1])
        for call in calls:
            self.assertEqual(call[0], "patch")
            self.assertIn("operationcapsules.ops.kubeactuary.dev", call)
            self.assertIn("--subresource", call)
            self.assertIn("status", call)
            self.assertNotIn("apply", call)
            self.assertNotIn("delete", call)
        report = json.loads(dry_run.stdout)
        self.assertEqual(report["mode"], "server-dry-run")
        self.assertEqual(report["writeExecution"], "disabled")
        self.assertEqual(report["patchScope"], "status")
        self.assertEqual(report["failed"], 0)

    def test_loop_repeats_read_and_status_dry_run_without_workload_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = {"items": [self.capsule([{"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"}])]}
            log_path = Path(tmpdir) / "kubectl-calls.json"
            kubectl = Path(tmpdir) / "kubectl"
            kubectl.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import json",
                        "import sys",
                        "from pathlib import Path",
                        f"log_path = Path({str(log_path)!r})",
                        "calls = json.loads(log_path.read_text()) if log_path.exists() else []",
                        "calls.append(sys.argv[1:])",
                        "log_path.write_text(json.dumps(calls))",
                        f"payload = {json.dumps(payload)!r}",
                        "if sys.argv[1] == 'get':",
                        "    print(payload)",
                        "    raise SystemExit(0)",
                        "if sys.argv[1] == 'patch':",
                        "    print('status dry-run ok')",
                        "    raise SystemExit(0)",
                        "print('unexpected kubectl call', file=sys.stderr)",
                        "raise SystemExit(9)",
                    ]
                )
            )
            kubectl.chmod(0o755)

            result = self.run_controller(
                "loop",
                "--kubectl",
                str(kubectl),
                "--iterations",
                "2",
                "--interval-seconds",
                "0",
            )
            calls = json.loads(log_path.read_text())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0], ["get", "operationcapsules.ops.kubeactuary.dev", "-o", "json", "--all-namespaces"])
        self.assertEqual(calls[2], ["get", "operationcapsules.ops.kubeactuary.dev", "-o", "json", "--all-namespaces"])
        for call in (calls[1], calls[3]):
            self.assertEqual(call[0], "patch")
            self.assertIn("--subresource", call)
            self.assertIn("status", call)
            self.assertIn("--dry-run=server", call)
            self.assertNotIn("apply", call)
            self.assertNotIn("delete", call)
        report = json.loads(result.stdout)
        self.assertEqual(report["mode"], "server-dry-run-loop")
        self.assertEqual(report["writeExecution"], "disabled")
        self.assertEqual(report["readExecution"], "kubectl-get")
        self.assertEqual(report["patchScope"], "status")
        self.assertEqual(report["iterations"], 2)
        self.assertEqual(report["failed"], 0)


if __name__ == "__main__":
    unittest.main()
