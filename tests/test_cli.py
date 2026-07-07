import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "kube-actuary"
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


class KubeActuaryCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(CLI), *args],
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
            evidence = capsule["status"]["evidence"]["read-auth"]
            self.assertFalse(evidence["ok"])
            self.assertEqual(evidence["reason"], "authorization-denied")
            self.assertTrue(evidence["summary"].startswith("authorization-denied:"))
            self.assertEqual(capsule["status"]["state"], "blocked")

    def test_collect_dry_run_attaches_server_dry_run_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            fake_kubectl = tmpdir_path / "kubectl"
            fake_kubectl.write_text("#!/bin/sh\nprintf 'configmap/demo server dry-run ok\\n'\n")
            fake_kubectl.chmod(0o755)
            manifest = tmpdir_path / "manifest.yaml"
            manifest.write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: demo\n")

            draft = self.run_cli(
                "draft",
                "--intent",
                "apply demo manifest",
                "--manifest",
                str(manifest),
                "--namespace",
                "default",
                "--actor",
                "test",
            )
            self.assertEqual(draft.returncode, 0, draft.stderr)
            capsule_path = tmpdir_path / "capsule.json"
            collected_path = tmpdir_path / "collected.json"
            capsule_path.write_text(draft.stdout)

            result = self.run_cli(
                "collect",
                "dry-run",
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
            evidence = capsule["status"]["evidence"]["server-dry-run"]
            self.assertTrue(evidence["ok"])
            self.assertEqual(evidence["collector"], "kubectl-server-dry-run")
            self.assertEqual(evidence["reason"], "command-ok")
            self.assertTrue(evidence["summary"].startswith("command-ok:"))
            self.assertIn("--dry-run=server", evidence["command"])
            self.assertEqual(evidence["sourceSha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())

    def test_collect_dry_run_and_diff_without_manifest_are_inapplicable(self):
        for collector_name, evidence_id in (("dry-run", "server-dry-run"), ("diff", "diff")):
            with self.subTest(collector=collector_name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    capsule_path = tmpdir_path / "capsule.json"
                    collected_path = tmpdir_path / "collected.json"
                    capsule_path.write_text(
                        json.dumps(
                            {
                                "metadata": {"id": "opcap-test"},
                                "spec": {
                                    "manifestPath": None,
                                    "requiredEvidence": [{"id": evidence_id}],
                                    "target": {
                                        "verb": "scale",
                                        "resource": "deployment",
                                        "namespace": "default",
                                        "scope": "namespace",
                                        "modifiesCluster": True,
                                    },
                                    "risk": {"level": "medium"},
                                },
                                "status": {"evidence": {}},
                            }
                        )
                    )

                    result = self.run_cli(
                        "collect",
                        collector_name,
                        str(capsule_path),
                        "--kubectl",
                        str(tmpdir_path / "missing-kubectl"),
                        "--out",
                        str(collected_path),
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    capsule = json.loads(collected_path.read_text())
                    evidence = capsule["status"]["evidence"][evidence_id]
                    self.assertFalse(evidence["ok"])
                    self.assertEqual(evidence["reason"], "manifest-required")
                    self.assertTrue(evidence["summary"].startswith("inapplicable:"))
                    self.assertTrue(evidence["inapplicable"])
                    self.assertEqual(capsule["status"]["state"], "blocked")

    def test_collect_manifest_collectors_normalize_missing_source(self):
        for collector_name, evidence_id in (("dry-run", "server-dry-run"), ("diff", "diff")):
            with self.subTest(collector=collector_name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    capsule_path = tmpdir_path / "capsule.json"
                    collected_path = tmpdir_path / "collected.json"
                    missing_manifest = tmpdir_path / "missing.yaml"
                    capsule_path.write_text(
                        json.dumps(
                            {
                                "metadata": {"id": "opcap-test"},
                                "spec": {
                                    "manifestPath": str(missing_manifest),
                                    "requiredEvidence": [{"id": evidence_id}],
                                    "target": {
                                        "verb": "manifest",
                                        "namespace": "default",
                                        "scope": "namespace",
                                        "modifiesCluster": True,
                                    },
                                    "risk": {"level": "medium"},
                                },
                                "status": {"evidence": {}},
                            }
                        )
                    )

                    result = self.run_cli(
                        "collect",
                        collector_name,
                        str(capsule_path),
                        "--kubectl",
                        str(tmpdir_path / "missing-kubectl"),
                        "--out",
                        str(collected_path),
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    capsule = json.loads(collected_path.read_text())
                    evidence = capsule["status"]["evidence"][evidence_id]
                    self.assertFalse(evidence["ok"])
                    self.assertEqual(evidence["reason"], "manifest-not-found")
                    self.assertTrue(evidence["summary"].startswith("missing-source: manifest file not found:"))

    def test_collect_dry_run_normalizes_command_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            fake_kubectl = tmpdir_path / "kubectl"
            fake_kubectl.write_text("#!/bin/sh\nprintf 'dry-run failed\\n' >&2\nexit 7\n")
            fake_kubectl.chmod(0o755)
            manifest = tmpdir_path / "manifest.yaml"
            manifest.write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: demo\n")
            capsule_path = tmpdir_path / "capsule.json"
            collected_path = tmpdir_path / "collected.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "manifestPath": str(manifest),
                            "requiredEvidence": [{"id": "server-dry-run"}],
                            "target": {
                                "verb": "manifest",
                                "namespace": "default",
                                "scope": "namespace",
                                "modifiesCluster": True,
                            },
                            "risk": {"level": "medium"},
                        },
                        "status": {"evidence": {}},
                    }
                )
            )

            result = self.run_cli(
                "collect",
                "dry-run",
                str(capsule_path),
                "--kubectl",
                str(fake_kubectl),
                "--out",
                str(collected_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            capsule = json.loads(collected_path.read_text())
            evidence = capsule["status"]["evidence"]["server-dry-run"]
            self.assertFalse(evidence["ok"])
            self.assertEqual(evidence["reason"], "command-failed")
            self.assertTrue(evidence["summary"].startswith("command-failed:"))
            self.assertEqual(evidence["exitCode"], 7)

    def test_collect_diff_exit_codes(self):
        for exit_code, expected_ok, expected_diff_found in (
            (0, True, False),
            (1, True, True),
            (2, False, False),
        ):
            with self.subTest(exit_code=exit_code):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    fake_kubectl = tmpdir_path / "kubectl"
                    fake_kubectl.write_text(f"#!/bin/sh\nprintf 'diff output\\n'\nexit {exit_code}\n")
                    fake_kubectl.chmod(0o755)
                    manifest = tmpdir_path / "manifest.yaml"
                    manifest.write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: demo\n")
                    capsule_path = tmpdir_path / "capsule.json"
                    collected_path = tmpdir_path / "collected.json"
                    capsule_path.write_text(
                        json.dumps(
                            {
                                "metadata": {"id": "opcap-test"},
                                "spec": {
                                    "manifestPath": str(manifest),
                                    "requiredEvidence": [{"id": "diff"}],
                                    "target": {
                                        "verb": "manifest",
                                        "namespace": "default",
                                        "scope": "namespace",
                                        "modifiesCluster": True,
                                    },
                                    "risk": {"level": "medium"},
                                },
                                "status": {"evidence": {}},
                            }
                        )
                    )

                    result = self.run_cli(
                        "collect",
                        "diff",
                        str(capsule_path),
                        "--kubectl",
                        str(fake_kubectl),
                        "--out",
                        str(collected_path),
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    capsule = json.loads(collected_path.read_text())
                    evidence = capsule["status"]["evidence"]["diff"]
                    self.assertEqual(evidence["ok"], expected_ok)
                    self.assertEqual(evidence["diffFound"], expected_diff_found)
                    self.assertEqual(evidence["exitCode"], exit_code)
                    expected_reason = {0: "command-ok", 1: "diff-found", 2: "command-failed"}[exit_code]
                    self.assertEqual(evidence["reason"], expected_reason)
                    self.assertTrue(evidence["summary"].startswith(f"{expected_reason}:"))

    def test_collect_rollback_command_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            capsule_path = tmpdir_path / "capsule.json"
            command_path = tmpdir_path / "with-command.json"
            manifest_path = tmpdir_path / "with-manifest.json"
            rollback_manifest = tmpdir_path / "rollback.yaml"
            rollback_manifest.write_text("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: demo\n")
            capsule_path.write_text(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "requiredEvidence": [{"id": "rollback"}],
                            "rollback": {"required": True, "provided": False},
                            "risk": {"level": "medium"},
                        },
                        "status": {"evidence": {}},
                    }
                )
            )

            command = self.run_cli(
                "collect",
                "rollback",
                str(capsule_path),
                "--command",
                "kubectl rollout undo deployment demo -n default",
                "--out",
                str(command_path),
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            command_capsule = json.loads(command_path.read_text())
            self.assertTrue(command_capsule["spec"]["rollback"]["provided"])
            command_evidence = command_capsule["status"]["evidence"]["rollback"]
            self.assertEqual(command_evidence["rollbackType"], "command")
            self.assertEqual(command_evidence["reason"], "rollback-command")

            manifest = self.run_cli(
                "collect",
                "rollback",
                str(capsule_path),
                "--manifest",
                str(rollback_manifest),
                "--out",
                str(manifest_path),
            )
            self.assertEqual(manifest.returncode, 0, manifest.stderr)
            manifest_capsule = json.loads(manifest_path.read_text())
            evidence = manifest_capsule["status"]["evidence"]["rollback"]
            self.assertEqual(evidence["rollbackType"], "manifest")
            self.assertEqual(evidence["reason"], "rollback-manifest")
            self.assertEqual(evidence["sourceSha256"], hashlib.sha256(rollback_manifest.read_bytes()).hexdigest())
            self.assertEqual(
                manifest_capsule["spec"]["rollback"]["manifestSha256"],
                hashlib.sha256(rollback_manifest.read_bytes()).hexdigest(),
            )

    def test_collect_rollback_normalizes_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            capsule_path = tmpdir_path / "capsule.json"
            collected_path = tmpdir_path / "collected.json"
            missing_manifest = tmpdir_path / "rollback.yaml"
            capsule_path.write_text(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "requiredEvidence": [{"id": "rollback"}],
                            "rollback": {"required": True, "provided": False},
                            "risk": {"level": "medium"},
                        },
                        "status": {"evidence": {}},
                    }
                )
            )

            result = self.run_cli(
                "collect",
                "rollback",
                str(capsule_path),
                "--manifest",
                str(missing_manifest),
                "--out",
                str(collected_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            capsule = json.loads(collected_path.read_text())
            evidence = capsule["status"]["evidence"]["rollback"]
            self.assertFalse(evidence["ok"])
            self.assertEqual(evidence["reason"], "manifest-not-found")
            self.assertTrue(evidence["summary"].startswith("missing-source: rollback manifest file not found:"))

    def test_collect_health_plan_attaches_post_checks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            capsule_path = tmpdir_path / "capsule.json"
            collected_path = tmpdir_path / "collected.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "metadata": {"id": "opcap-test"},
                        "spec": {
                            "requiredEvidence": [{"id": "post-checks"}],
                            "postChecks": ["rollout status succeeds", "no new warning events"],
                            "risk": {"level": "medium"},
                        },
                        "status": {"evidence": {}},
                    }
                )
            )

            result = self.run_cli("collect", "health-plan", str(capsule_path), "--out", str(collected_path))

            self.assertEqual(result.returncode, 0, result.stderr)
            capsule = json.loads(collected_path.read_text())
            evidence = capsule["status"]["evidence"]["post-checks"]
            self.assertTrue(evidence["ok"])
            self.assertEqual(evidence["reason"], "health-plan")
            self.assertEqual(evidence["checks"], ["rollout status succeeds", "no new warning events"])

    def test_digest_ignores_status_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            capsule_path = tmpdir_path / "capsule.json"
            attached_path = tmpdir_path / "attached.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "apiVersion": "kubeactuary.dev/v0alpha1",
                        "kind": "OperationCapsule",
                        "metadata": {"id": "opcap-test", "createdAt": "2026-07-01T00:00:00Z"},
                        "spec": {
                            "requiredEvidence": [{"id": "intent"}],
                            "risk": {"level": "low"},
                        },
                        "status": {"state": "drafted", "evidence": {}},
                    }
                )
            )

            before = self.run_cli("digest", str(capsule_path))
            self.assertEqual(before.returncode, 0, before.stderr)
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
            after = self.run_cli("digest", str(attached_path))
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertEqual(before.stdout.strip(), after.stdout.strip())

    def test_validate_passes_valid_example(self):
        result = self.run_cli("validate", str(ROOT / "examples" / "apply-configmap.preflight.capsule.json"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validation: passed", result.stdout)

    def test_validate_reports_missing_required_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            capsule = json.loads((ROOT / "examples" / "apply-configmap.preflight.capsule.json").read_text())
            del capsule["spec"]["actor"]
            path.write_text(json.dumps(capsule))

            result = self.run_cli("validate", str(path))

        self.assertEqual(result.returncode, 1)
        self.assertIn("validation: failed", result.stdout)
        self.assertIn("validation-error: spec.actor: is required", result.stdout)

    def test_validate_json_output_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            capsule = json.loads((ROOT / "examples" / "apply-configmap.preflight.capsule.json").read_text())
            capsule["spec"]["target"]["scope"] = "everywhere"
            path.write_text(json.dumps(capsule))

            result = self.run_cli("validate", str(path), "--format", "json")

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["path"], "spec.target.scope")

    def test_doctor_warns_when_kubectl_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("doctor", "--kubectl", str(Path(tmpdir) / "missing-kubectl"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doctor: ok-with-warnings", result.stdout)
        self.assertIn("warning: kubectl: kubectl not found", result.stdout)

    def test_doctor_reads_fake_kubectl_client_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_kubectl = Path(tmpdir) / "kubectl"
            fake_kubectl.write_text(
                "#!/bin/sh\n"
                "printf '{\"clientVersion\":{\"gitVersion\":\"v1.30.1\"}}\\n'\n"
            )
            fake_kubectl.chmod(0o755)

            result = self.run_cli("doctor", "--kubectl", str(fake_kubectl), "--server-version", "v1.30.2")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doctor: ok", result.stdout)
        self.assertIn("check: kubectl-client-version: kubectl client version: v1.30.1", result.stdout)
        self.assertIn("check: kubectl-skew: client v1.30.1 is within one minor of server v1.30.2", result.stdout)

    def test_doctor_json_reports_kubectl_skew_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_kubectl = Path(tmpdir) / "kubectl"
            fake_kubectl.write_text(
                "#!/bin/sh\n"
                "printf '{\"clientVersion\":{\"gitVersion\":\"v1.27.0\"}}\\n'\n"
            )
            fake_kubectl.chmod(0o755)

            result = self.run_cli(
                "doctor",
                "--kubectl",
                str(fake_kubectl),
                "--server-version",
                "v1.30.0",
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"], "ok-with-warnings")
        skew = next(check for check in payload["checks"] if check["id"] == "kubectl-skew")
        self.assertEqual(skew["status"], "warn")

    def test_full_manifest_evidence_flow_can_open_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            fake_kubectl = tmpdir_path / "kubectl"
            fake_kubectl.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  auth) printf 'yes\\n'; exit 0 ;;\n"
                "  apply) printf 'server dry-run ok\\n'; exit 0 ;;\n"
                "  diff) printf 'diff output\\n'; exit 1 ;;\n"
                "esac\n"
                "printf 'unexpected command: %s\\n' \"$1\" >&2\n"
                "exit 9\n"
            )
            fake_kubectl.chmod(0o755)
            manifest = tmpdir_path / "manifest.yaml"
            manifest.write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: demo\n")
            paths = [tmpdir_path / f"step-{i}.json" for i in range(8)]

            draft = self.run_cli(
                "draft",
                "--intent",
                "apply demo config",
                "--manifest",
                str(manifest),
                "--namespace",
                "default",
                "--actor",
                "test",
                "--out",
                str(paths[0]),
            )
            self.assertEqual(draft.returncode, 0, draft.stderr)

            steps = [
                (
                    "attach-evidence",
                    str(paths[0]),
                    "--id",
                    "intent",
                    "--summary",
                    "intent reviewed",
                    "--actor",
                    "reviewer",
                    "--out",
                    str(paths[1]),
                ),
                (
                    "attach-evidence",
                    str(paths[1]),
                    "--id",
                    "parsed-target",
                    "--summary",
                    "manifest target reviewed",
                    "--actor",
                    "reviewer",
                    "--out",
                    str(paths[2]),
                ),
                (
                    "collect",
                    "auth",
                    str(paths[2]),
                    "--kubectl",
                    str(fake_kubectl),
                    "--out",
                    str(paths[3]),
                ),
                (
                    "collect",
                    "dry-run",
                    str(paths[3]),
                    "--kubectl",
                    str(fake_kubectl),
                    "--out",
                    str(paths[4]),
                ),
                (
                    "collect",
                    "diff",
                    str(paths[4]),
                    "--kubectl",
                    str(fake_kubectl),
                    "--out",
                    str(paths[5]),
                ),
                (
                    "collect",
                    "rollback",
                    str(paths[5]),
                    "--command",
                    "kubectl delete configmap demo -n default",
                    "--out",
                    str(paths[6]),
                ),
                ("collect", "health-plan", str(paths[6]), "--out", str(paths[7])),
            ]
            for step in steps:
                result = self.run_cli(*step)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            gate = self.run_cli("gate", str(paths[7]))
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            self.assertIn("gate: open", gate.stdout)

    def test_help_command_prints_human_reference_sections(self):
        result = self.run_cli("help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("USAGE", result.stdout)
        self.assertIn("CORE COMMANDS", result.stdout)
        self.assertIn("COLLECTOR COMMANDS", result.stdout)
        self.assertIn("HELP TOPICS", result.stdout)
        self.assertIn("SAFETY MODEL", result.stdout)
        self.assertIn("LEARN MORE", result.stdout)
        self.assertIn("collect dry-run:", result.stdout)
        self.assertIn("kube-actuary help agents --format json", result.stdout)
        self.assertIn("validate:", result.stdout)

    def test_help_safety_documents_execution_boundary(self):
        result = self.run_cli("help", "safety")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SAFE CLUSTER CALLS", result.stdout)
        self.assertIn("kubectl apply --dry-run=server -f <manifest>", result.stdout)
        self.assertIn("NEVER EXECUTED BY KUBEACTUARY", result.stdout)
        self.assertIn("spec.proposedCommand", result.stdout)

    def test_help_agents_json_is_machine_readable(self):
        result = self.run_cli("help", "agents", "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "kube-actuary")
        self.assertEqual(payload["version"], "0.9.5")
        self.assertEqual(payload["selectedTopic"], "agents")
        self.assertIn("commands", payload)
        self.assertIn("agentContract", payload)
        self.assertTrue(all(command["clusterWrites"] is False for command in payload["commands"]))
        validate = next(command for command in payload["commands"] if command["name"] == "validate")
        self.assertEqual(validate["clusterAccess"], "none")
        doctor = next(command for command in payload["commands"] if command["name"] == "doctor")
        self.assertEqual(doctor["clusterAccess"], "kubectl version --client=true -o json")
        dry_run = next(command for command in payload["commands"] if command["name"] == "collect dry-run")
        self.assertEqual(dry_run["clusterAccess"], "kubectl apply --dry-run=server -f <manifest>")
        self.assertIn("the capsule spec.proposedCommand", payload["agentContract"]["neverExecutes"])
        self.assertEqual(payload["agentContract"]["exitCodes"]["gate"]["0"], "gate is open")
        self.assertEqual(payload["agentContract"]["exitCodes"]["validate"]["1"], "capsule structure is invalid")
        self.assertEqual(payload["agentContract"]["exitCodes"]["doctor"]["1"], "a required local check failed")

    def test_help_agents_json_has_versioned_compatibility_contract(self):
        result = self.run_cli("help", "agents", "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schemaVersion"], "kube-actuary.help.v1")
        compatibility = payload["compatibility"]
        self.assertEqual(compatibility["schemaVersion"], "kube-actuary.help.v1")
        self.assertEqual(compatibility["introducedIn"], "0.2.3")
        self.assertEqual(compatibility["backwardCompatibleUntil"], "1.0.0")
        for field in compatibility["requiredTopLevelFields"]:
            self.assertIn(field, payload)
        for command in payload["commands"]:
            with self.subTest(command=command["name"]):
                for field in compatibility["requiredCommandFields"]:
                    self.assertIn(field, command)
                self.assertIsInstance(command["name"], str)
                self.assertIsInstance(command["summary"], str)
                self.assertIsInstance(command["clusterAccess"], str)
                self.assertIsInstance(command["clusterWrites"], bool)
                self.assertIsInstance(command["capsuleWrites"], bool)
                self.assertIsInstance(command["examples"], list)

    def test_help_agents_text_prints_schema_version(self):
        result = self.run_cli("help", "agents")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("schema version: kube-actuary.help.v1", result.stdout)
        self.assertIn("compatibility.requiredCommandFields", result.stdout)

    def test_version_reports_v095(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kube-actuary 0.9.5", result.stdout)

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
        self.assertIn('status:', result.stdout)
        self.assertIn('phase: "GateOpen"', result.stdout)
        self.assertIn('gate: "Open"', result.stdout)
        self.assertIn('type: "EvidenceComplete"', result.stdout)
        self.assertIn('type: "RollbackReady"', result.stdout)

    def test_render_crd_preserves_evidence_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "capsule.json"
            path.write_text(
                json.dumps(
                    {
                        "apiVersion": "kubeactuary.dev/v0alpha1",
                        "kind": "OperationCapsule",
                        "metadata": {"id": "opcap-test", "createdAt": "2026-07-01T00:00:00Z"},
                        "spec": {
                            "intent": "apply demo",
                            "actor": "test",
                            "target": {
                                "verb": "manifest",
                                "scope": "namespace",
                                "namespace": "default",
                                "modifiesCluster": True,
                            },
                            "risk": {"level": "medium", "reasons": ["cluster state may be modified"]},
                            "requiredEvidence": [{"id": "server-dry-run", "description": "dry-run succeeds"}],
                            "rollback": {"required": True, "provided": False},
                            "postChecks": ["rollout status succeeds"],
                        },
                        "status": {
                            "state": "blocked",
                            "evidence": {
                                "server-dry-run": {
                                    "ok": False,
                                    "summary": "command-failed: kubectl returned 7",
                                    "actor": "collector",
                                    "attachedAt": "2026-07-01T00:00:00Z",
                                    "collector": "kubectl-server-dry-run",
                                    "reason": "command-failed",
                                }
                            },
                        },
                    }
                )
            )

            result = self.run_cli("render-crd", str(path), "--name", "demo", "--namespace", "default")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('reason: "command-failed"', result.stdout)

    def test_render_crd_status_conditions_show_blocked_capsule(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "capsule.json"
            path.write_text(
                json.dumps(
                    {
                        "apiVersion": "kubeactuary.dev/v0alpha1",
                        "kind": "OperationCapsule",
                        "metadata": {"id": "opcap-test", "createdAt": "2026-07-01T00:00:00Z"},
                        "spec": {
                            "intent": "apply demo",
                            "actor": "test",
                            "target": {
                                "verb": "manifest",
                                "scope": "namespace",
                                "namespace": "default",
                                "modifiesCluster": True,
                            },
                            "risk": {"level": "medium", "reasons": ["cluster state may be modified"]},
                            "requiredEvidence": [
                                {"id": "server-dry-run", "description": "dry-run succeeds"},
                                {"id": "rollback", "description": "rollback attached"},
                            ],
                            "rollback": {"required": True, "provided": False},
                            "postChecks": ["rollout status succeeds"],
                        },
                        "status": {
                            "state": "blocked",
                            "evidence": {
                                "server-dry-run": {
                                    "ok": False,
                                    "summary": "command-failed: kubectl returned 7",
                                    "actor": "collector",
                                    "attachedAt": "2026-07-01T00:00:00Z",
                                }
                            },
                        },
                    }
                )
            )

            result = self.run_cli("render-crd", str(path), "--name", "demo", "--namespace", "default")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('phase: "Blocked"', result.stdout)
        self.assertIn('gate: "Closed"', result.stdout)
        self.assertIn('- "rollback"', result.stdout)
        self.assertIn('type: "Blocked"', result.stdout)
        self.assertIn('status: "True"', result.stdout)
        self.assertIn('type: "RollbackReady"', result.stdout)
        self.assertIn('reason: "RollbackMissing"', result.stdout)

    def test_crd_schema_freezes_v030_fields(self):
        crd = (ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml").read_text()
        for field in (
            "proposedAction:",
            "requiredEvidence:",
            "evidence:",
            "postChecks:",
            "rollback:",
            "ttlSecondsAfterFinished:",
            "missingEvidence:",
            "failedEvidence:",
            "conditions:",
            "EvidenceComplete",
            "GateOpen",
            "Blocked",
            "RollbackReady",
            "Expired",
        ):
            with self.subTest(field=field):
                self.assertIn(field, crd)


if __name__ == "__main__":
    unittest.main()
