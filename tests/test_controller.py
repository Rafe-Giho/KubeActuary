import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"


class ControllerReconcileTests(unittest.TestCase):
    def run_controller(self, *args):
        return subprocess.run(
            [sys.executable, str(CONTROLLER), *args],
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


if __name__ == "__main__":
    unittest.main()
