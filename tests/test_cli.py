import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "kube-actuary"


class KubeActuaryCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_draft_classifies_prod_scale_as_high_risk(self):
        result = self.run_cli(
            "draft",
            "--intent",
            "scale checkout api",
            "--command",
            "kubectl scale deployment checkout-api --replicas=6 -n prod",
            "--actor",
            "test",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        capsule = json.loads(result.stdout)
        self.assertEqual(capsule["spec"]["target"]["verb"], "scale")
        self.assertEqual(capsule["spec"]["target"]["namespace"], "prod")
        self.assertEqual(capsule["spec"]["risk"]["level"], "high")

    def test_read_only_get_is_low_risk(self):
        result = self.run_cli(
            "draft",
            "--intent",
            "inspect pods",
            "--command",
            "kubectl get pods -n default",
            "--actor",
            "test",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        capsule = json.loads(result.stdout)
        self.assertFalse(capsule["spec"]["target"]["modifiesCluster"])
        self.assertEqual(capsule["spec"]["risk"]["level"], "low")

    def test_verify_fails_when_evidence_is_missing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write(
                json.dumps(
                    {
                        "spec": {
                            "requiredEvidence": [
                                {"id": "intent"},
                                {"id": "write-auth"},
                            ]
                        },
                        "status": {"evidence": {"intent": {"ok": True}}},
                    }
                )
            )
            path = tmp.name

        result = self.run_cli("verify", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing-evidence: write-auth", result.stdout)

    def test_attach_evidence_can_make_capsule_verifiable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capsule_path = Path(tmpdir) / "capsule.json"
            attached_path = Path(tmpdir) / "attached.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "requiredEvidence": [
                                {"id": "intent"},
                            ],
                            "risk": {"level": "low"},
                            "proposedCommand": "kubectl get pods",
                        },
                        "status": {"evidence": {}},
                    }
                )
            )

            attach = self.run_cli(
                "attach-evidence",
                str(capsule_path),
                "--id",
                "intent",
                "--summary",
                "intent reviewed",
                "--actor",
                "test",
                "--out",
                str(attached_path),
            )
            self.assertEqual(attach.returncode, 0, attach.stderr)

            verify = self.run_cli("verify", str(attached_path))
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

            gated = self.run_cli("gate", str(attached_path))
            self.assertEqual(gated.returncode, 0, gated.stdout + gated.stderr)
            self.assertIn("gate: open", gated.stdout)

    def test_gate_closes_on_failed_evidence(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "requiredEvidence": [{"id": "intent"}],
                            "risk": {"level": "low"},
                        },
                        "status": {"evidence": {"intent": {"ok": False}}},
                    }
                )
            )
            path = tmp.name

        result = self.run_cli("gate", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("gate: closed", result.stdout)
        self.assertIn("failed evidence intent", result.stdout)

    def test_collect_auth_attaches_read_auth_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            fake_kubectl = tmpdir_path / "kubectl"
            fake_kubectl.write_text("#!/bin/sh\nprintf 'yes\\n'\n")
            fake_kubectl.chmod(0o755)

            draft = self.run_cli(
                "draft",
                "--intent",
                "inspect pods",
                "--command",
                "kubectl get pods -n default",
                "--actor",
                "test",
            )
            self.assertEqual(draft.returncode, 0, draft.stderr)
            capsule_path = tmpdir_path / "capsule.json"
            capsule_path.write_text(draft.stdout)
            collected_path = tmpdir_path / "collected.json"

            result = self.run_cli(
                "collect",
                "auth",
                str(capsule_path),
                "--kubectl",
                str(fake_kubectl),
                "--actor",
                "collector",
                "--out",
                str(collected_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            capsule = json.loads(collected_path.read_text())
            evidence = capsule["status"]["evidence"]["read-auth"]
            self.assertTrue(evidence["ok"])
            self.assertEqual(evidence["collector"], "kubectl-auth-can-i")
            self.assertEqual(capsule["status"]["state"], "evidence-attached")

    def test_collect_auth_failed_can_i_blocks_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            fake_kubectl = tmpdir_path / "kubectl"
            fake_kubectl.write_text("#!/bin/sh\nprintf 'no\\n'\nexit 1\n")
            fake_kubectl.chmod(0o755)
            capsule_path = tmpdir_path / "capsule.json"
            collected_path = tmpdir_path / "collected.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "requiredEvidence": [{"id": "read-auth"}],
                            "target": {
                                "verb": "get",
                                "resource": "pods",
                                "namespace": "default",
                                "scope": "namespace",
                                "modifiesCluster": False,
                            },
                            "risk": {"level": "low"},
                        },
                        "status": {"evidence": {}},
                    }
                )
            )

            result = self.run_cli(
                "collect",
                "auth",
                str(capsule_path),
                "--kubectl",
                str(fake_kubectl),
                "--out",
                str(collected_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            capsule = json.loads(collected_path.read_text())
            self.assertFalse(capsule["status"]["evidence"]["read-auth"]["ok"])
            self.assertEqual(capsule["status"]["state"], "blocked")

    def test_version_reports_v010(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kube-actuary 0.1.0", result.stdout)

    def test_render_crd_outputs_operationcapsule_yaml(self):
        result = self.run_cli(
            "render-crd",
            str(ROOT / "examples" / "read-pods.verified.capsule.json"),
            "--name",
            "read-pods",
            "--namespace",
            "default",
            "--ttl-seconds-after-finished",
            "3600",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('apiVersion: "ops.kubeactuary.dev/v1alpha1"', result.stdout)
        self.assertIn('kind: "OperationCapsule"', result.stdout)
        self.assertIn('name: "read-pods"', result.stdout)
        self.assertIn('namespace: "default"', result.stdout)
        self.assertIn('proposedAction:', result.stdout)
        self.assertIn('requiredEvidence:', result.stdout)
        self.assertIn('ttlSecondsAfterFinished: 3600', result.stdout)


if __name__ == "__main__":
    unittest.main()
