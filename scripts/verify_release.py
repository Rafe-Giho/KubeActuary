#!/usr/bin/env python3
"""Run repeatable KubeActuary release verification suites."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    expected_returncode: int = 0
    contains: tuple[str, ...] = ()
    json_probe: str | None = None


COMMON_CHECKS = (
    Check(
        "unit tests",
        ("python3", "-B", "-m", "unittest", "discover", "-s", "tests"),
        contains=("OK",),
    ),
    Check(
        "version",
        ("python3", "-B", "bin/kube-actuary", "--version"),
        contains=("kube-actuary 0.2.0",),
    ),
    Check(
        "top-level help",
        ("python3", "-B", "bin/kube-actuary", "help"),
        contains=("USAGE", "CORE COMMANDS", "COLLECTOR COMMANDS", "SAFETY MODEL"),
    ),
    Check(
        "agent help json",
        ("python3", "-B", "bin/kube-actuary", "help", "agents", "--format", "json"),
        json_probe="agent_help",
    ),
    Check(
        "agent help contract",
        ("python3", "-B", "scripts/verify_agent_help_contract.py"),
        contains=("agent-help-contract: passed", "schemaVersion: kube-actuary.help.v1"),
    ),
    Check(
        "agent examples",
        ("python3", "-B", "scripts/verify_agent_examples.py"),
        contains=("agent-examples: passed", "runbooks: 2", "writes: disabled"),
    ),
    Check(
        "collect help",
        ("python3", "-B", "bin/kube-actuary", "collect", "--help"),
        contains=("auth", "dry-run", "diff", "rollback", "health-plan"),
    ),
    Check(
        "validate example",
        ("python3", "-B", "bin/kube-actuary", "validate", "examples/apply-configmap.preflight.capsule.json"),
        contains=("validation: passed",),
    ),
    Check(
        "doctor missing kubectl",
        ("python3", "-B", "bin/kube-actuary", "doctor", "--kubectl", "/definitely/missing/kubectl"),
        contains=("doctor: ok-with-warnings", "warning: kubectl: kubectl not found"),
    ),
    Check(
        "release notes dry run",
        ("python3", "-B", "scripts/generate_release_notes.py", "--version", "0.2.0", "--date", "2026-07-06", "--output", "-"),
        contains=("# KubeActuary 0.2.0 Release Notes", "## Verification", "## Rollback"),
    ),
    Check(
        "release taskboard",
        ("python3", "-B", "scripts/verify_release_taskboard.py"),
        contains=("release-taskboard: passed", "release-checks:"),
    ),
    Check(
        "release progress",
        ("python3", "-B", "scripts/verify_release_progress.py"),
        contains=("release-progress: passed", "verify: 16", "checks: 83"),
    ),
    Check(
        "version worklist",
        ("python3", "-B", "scripts/verify_version_worklist.py"),
        contains=("version-worklist: passed", "capture-ready: 4", "blocked-by-tools: 12"),
    ),
    Check(
        "version blockers",
        ("python3", "-B", "scripts/verify_version_blockers.py"),
        contains=("version-blockers: passed", "blocked-items: 3", "record: metadata"),
    ),
    Check(
        "version unblock plan",
        ("python3", "-B", "scripts/verify_version_unblock_plan.py"),
        contains=("version-unblock-plan: passed", "actions: 3", "record: metadata"),
    ),
    Check(
        "next unblock action",
        ("python3", "-B", "scripts/verify_next_unblock_action.py"),
        contains=("next-unblock-action: passed", "target: kind", "record: metadata"),
    ),
    Check(
        "next unblock action runner",
        ("python3", "-B", "scripts/verify_next_unblock_action_runner.py"),
        contains=("next-unblock-action-runner: passed", "mode: plan,run", "record: metadata"),
    ),
    Check(
        "external gate plan",
        ("python3", "-B", "scripts/verify_external_gate_plan.py"),
        contains=("external-gate-plan: passed", "verify-gates: 16", "doing: 0"),
    ),
    Check(
        "external gate command safety",
        ("python3", "-B", "scripts/verify_external_gate_command_safety.py"),
        contains=("external-gate-command-safety: passed", "writes: disabled"),
    ),
    Check(
        "external gate evidence",
        ("python3", "-B", "scripts/verify_external_gate_evidence.py"),
        contains=("external-gate-evidence: passed", "smoke-covered: 12", "supplemental-covered: 16"),
    ),
    Check(
        "external evidence builder",
        ("python3", "-B", "scripts/verify_external_evidence_builder.py"),
        contains=("external-evidence-builder: passed", "kinds: 3"),
    ),
    Check(
        "external evidence bundle",
        ("python3", "-B", "scripts/verify_external_evidence_bundle.py"),
        contains=("external-evidence-bundle: passed", "closure: complete"),
    ),
    Check(
        "release evidence directory",
        ("python3", "-B", "scripts/verify_release_evidence_directory.py"),
        contains=("release-evidence-directory: passed", "closure: complete", "metadata: ignored"),
    ),
    Check(
        "release evidence status",
        ("python3", "-B", "scripts/verify_release_evidence_status.py"),
        contains=("release-evidence-status: passed", "complete: ok", "record: metadata"),
    ),
    Check(
        "next version task runner",
        ("python3", "-B", "scripts/verify_next_version_task_runner.py"),
        contains=("next-version-task-runner: passed", "mode: plan,run", "record: metadata"),
    ),
    Check(
        "version iteration advance",
        ("python3", "-B", "scripts/verify_version_iteration_advance.py"),
        contains=(
            "version-iteration-advance: passed",
            "history-runs: 2",
            "advance-record: metadata",
            "blocker-ledger: metadata",
        ),
    ),
    Check(
        "clean artifacts",
        ("python3", "-B", "scripts/verify_clean_artifacts.py"),
        contains=("clean-artifacts: passed", "python-cache-dirs: 0", "python-bytecode-files: 0"),
    ),
    Check(
        "crd compatibility smoke",
        ("python3", "-B", "scripts/verify_crd_compatibility.py"),
        contains=("crd-compatibility: passed", "upstream-minors: 1.36, 1.35, 1.34"),
    ),
    Check(
        "crd upgrade fixtures",
        ("python3", "-B", "scripts/verify_crd_upgrade_fixtures.py"),
        contains=("crd-upgrade-fixtures: passed", "operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml"),
    ),
    Check(
        "crd explain quality",
        ("python3", "-B", "scripts/verify_crd_explain_quality.py"),
        contains=("crd-explain-quality: passed", "commands: 7"),
    ),
    Check(
        "conformance suite",
        ("python3", "-B", "scripts/verify_conformance_suite.py"),
        contains=("conformance-suite: passed", "upstream-minors: 1.36, 1.35, 1.34"),
    ),
    Check(
        "managed kubernetes smoke",
        ("python3", "-B", "scripts/verify_managed_kubernetes_smoke.py"),
        contains=("managed-kubernetes-smoke: passed", "providers: eks, gke, aks", "mode: offline-plan"),
    ),
    Check(
        "controller contract",
        ("python3", "-B", "scripts/verify_controller_contract.py"),
        contains=("controller-contract: passed", "patch-scope: status"),
    ),
    Check(
        "controller rbac",
        ("python3", "-B", "scripts/verify_controller_rbac.py"),
        contains=(
            "controller-rbac: passed",
            "namespace-mode: Role/RoleBinding",
            "cluster-mode: ClusterRole/ClusterRoleBinding",
            "status-write-only: operationcapsules/status",
        ),
    ),
    Check(
        "controller runtime",
        ("python3", "-B", "scripts/verify_controller_runtime_contract.py"),
        contains=(
            "controller-runtime: passed",
            "health: ok",
            "ready: ok",
            "metrics: prometheus-text",
            "leader-election: leases.coordination.k8s.io",
        ),
    ),
    Check(
        "controller deployment",
        ("python3", "-B", "scripts/verify_controller_deployment.py"),
        contains=("controller-deployment: passed", "runtime: serve", "probes: healthz, readyz"),
    ),
    Check(
        "controller patch plan",
        ("python3", "-B", "scripts/verify_controller_patch_plan.py"),
        contains=("controller-patch-plan: passed", "patch-scope: status", "write-execution: disabled"),
    ),
    Check(
        "controller sync",
        ("python3", "-B", "scripts/verify_controller_sync.py"),
        contains=("controller-sync: passed", "read: operationcapsules", "write-execution: disabled"),
    ),
    Check(
        "controller status apply",
        ("python3", "-B", "scripts/verify_controller_status_apply.py"),
        contains=("controller-status-apply: passed", "default-mode: server-dry-run", "write-execution: disabled"),
    ),
    Check(
        "controller loop",
        ("python3", "-B", "scripts/verify_controller_loop.py"),
        contains=("controller-loop: passed", "default-mode: server-dry-run", "write-execution: disabled"),
    ),
    Check(
        "controller resource budget",
        ("python3", "-B", "scripts/verify_controller_resource_budget.py"),
        contains=(
            "controller-resource-budget: passed",
            "idle-cpu-budget: <50m",
            "idle-memory-budget: <64Mi",
            "measurement-harness: kubectl top",
        ),
    ),
    Check(
        "controller resource capture",
        ("python3", "-B", "scripts/verify_controller_resource_capture.py"),
        contains=("controller-resource-capture: passed", "cluster-writes: disabled", "supplemental: buildable"),
    ),
    Check(
        "lightweight cluster smoke",
        ("python3", "-B", "scripts/verify_lightweight_cluster_smoke.py"),
        contains=(
            "lightweight-cluster-smoke: passed",
            "providers: kind, minikube, microk8s, k3s",
            "mode: offline-plan",
        ),
    ),
    Check(
        "helm chart",
        ("python3", "-B", "scripts/verify_helm_chart.py"),
        contains=("helm-chart: passed", "crd: included", "controller: optional"),
    ),
    Check(
        "kustomize",
        ("python3", "-B", "scripts/verify_kustomize.py"),
        contains=("kustomize: passed", "base: crd", "overlay: controller-namespace", "overlay: controller-cluster"),
    ),
    Check(
        "release archives",
        ("python3", "-B", "scripts/verify_release_archives.py"),
        contains=(
            "release-archives: passed",
            "targets: linux-amd64, linux-arm64, darwin-amd64, darwin-arm64",
            "sha256: verified",
            "install-smoke: passed",
        ),
    ),
    Check(
        "krew manifest",
        ("python3", "-B", "scripts/verify_krew_manifest.py"),
        contains=(
            "krew-manifest: passed",
            "plugin: actuary",
            "platforms: linux-amd64, linux-arm64, darwin-amd64, darwin-arm64",
        ),
    ),
    Check(
        "supply chain",
        ("python3", "-B", "scripts/verify_supply_chain.py"),
        contains=("supply-chain: passed", "provenance-subjects: 4", "archive-digests: verified"),
    ),
    Check(
        "security docs",
        ("python3", "-B", "scripts/verify_security_docs.py"),
        contains=("security-docs: passed", "security-policy: present", "threat-model: present"),
    ),
    Check(
        "api freeze",
        ("python3", "-B", "scripts/verify_api_freeze.py"),
        contains=("api-freeze: passed", "policy: additive-only", "breaking-schema-diff: guarded"),
    ),
    Check(
        "docs freeze",
        ("python3", "-B", "scripts/verify_docs_freeze.py"),
        contains=("docs-freeze: passed", "public-examples: 11 checked", "writes: disabled"),
    ),
    Check(
        "live validation readiness",
        ("python3", "-B", "scripts/verify_live_validation_readiness.py"),
        contains=("live-validation-readiness: passed", "mode: inventory-only", "tool-ready-gates:", "cluster-writes: disabled"),
    ),
    Check(
        "live validation queue",
        ("python3", "-B", "scripts/verify_live_validation_queue.py"),
        contains=("live-validation-queue: passed", "tool-ready:", "cluster-writes: disabled"),
    ),
    Check(
        "live validation queue safety",
        ("python3", "-B", "scripts/verify_live_validation_queue_safety.py"),
        contains=("live-validation-queue-safety: passed", "writes: disabled"),
    ),
    Check(
        "live evidence directory scaffold",
        ("python3", "-B", "scripts/verify_live_evidence_directory_scaffold.py"),
        contains=("live-evidence-directory-scaffold: passed", "cluster-writes: disabled", "environment-probe: metadata"),
    ),
    Check(
        "live evidence schema",
        ("python3", "-B", "scripts/verify_live_evidence_schema.py"),
        contains=("live-evidence-schema: passed", "schemas: 5"),
    ),
    Check(
        "live evidence manifest",
        ("python3", "-B", "scripts/verify_live_evidence_manifest.py"),
        contains=("live-evidence-manifest: passed", "reports: 5"),
    ),
    Check(
        "live evidence coverage",
        ("python3", "-B", "scripts/verify_live_evidence_coverage.py"),
        contains=("live-evidence-coverage: passed", "required-providers: 7"),
    ),
    Check(
        "project governance",
        ("python3", "-B", "scripts/verify_project_governance.py"),
        contains=("project-governance: passed", "license: MIT", "contributing: present"),
    ),
    Check(
        "airgap bundle",
        ("python3", "-B", "scripts/verify_airgap_bundle.py"),
        contains=("airgap-bundle: passed", "release-artifacts: verified", "offline-checklist: present"),
    ),
    Check(
        "kyverno adapter",
        ("python3", "-B", "scripts/verify_kyverno_adapter.py"),
        contains=("kyverno-adapter: passed", "pass-fixture: policy-pass", "fail-fixture: policy-fail"),
    ),
    Check(
        "opa adapter",
        ("python3", "-B", "scripts/verify_opa_adapter.py"),
        contains=("opa-adapter: passed", "pass-fixture: policy-pass", "fail-fixture: policy-fail"),
    ),
    Check(
        "kube-linter adapter",
        ("python3", "-B", "scripts/verify_kube_linter_adapter.py"),
        contains=("kube-linter-adapter: passed", "pass-fixture: policy-pass", "fail-fixture: policy-fail"),
    ),
    Check(
        "kube-score adapter",
        ("python3", "-B", "scripts/verify_kube_score_adapter.py"),
        contains=("kube-score-adapter: passed", "pass-fixture: policy-pass", "fail-fixture: policy-fail"),
    ),
    Check(
        "pluto adapter",
        ("python3", "-B", "scripts/verify_pluto_adapter.py"),
        contains=("pluto-adapter: passed", "pass-fixture: api-compatible", "fail-fixture: deprecated-api-found"),
    ),
    Check(
        "adapter contract",
        ("python3", "-B", "scripts/verify_adapter_contract.py"),
        contains=("adapter-contract: passed", "fixtures: 10", "severity: normalized"),
    ),
    Check(
        "mcp contract",
        ("python3", "-B", "scripts/verify_mcp_contract.py"),
        contains=("mcp-contract: passed", "safe-tools: 5", "execute-tool: disabled"),
    ),
    Check(
        "mcp docs",
        ("python3", "-B", "scripts/verify_mcp_docs.py"),
        contains=("mcp-docs: passed", "client-config: examples/mcp-client-config.json", "execute-tool: disabled"),
    ),
    Check(
        "execute disabled",
        ("python3", "-B", "scripts/verify_execute_disabled.py"),
        contains=("execute-disabled: passed", "cli-execute: absent", "mcp-execute: disabled"),
    ),
    Check(
        "admission webhook",
        ("python3", "-B", "scripts/verify_admission_webhook.py"),
        contains=("admission-webhook: passed", "failurePolicy: Ignore", "evidence-schema: kube-actuary.admission-kind-smoke.v1"),
    ),
    Check(
        "admission policy",
        ("python3", "-B", "scripts/verify_admission_policy.py"),
        contains=("admission-policy: passed", "allow-fixtures: 2", "deny-fixtures: 2"),
    ),
    Check(
        "admission digest gate",
        ("python3", "-B", "scripts/verify_admission_digest_gate.py"),
        contains=("admission-digest-gate: passed", "allow-fixtures: 1", "tamper-fixtures: 2"),
    ),
    Check(
        "admission audit",
        ("python3", "-B", "scripts/verify_admission_audit.py"),
        contains=("admission-audit: passed", "audit-fixtures: 2", "runbook: present"),
    ),
    Check(
        "admission response",
        ("python3", "-B", "scripts/verify_admission_response.py"),
        contains=("admission-response: passed", "responses: 2", "auditAnnotations: present"),
    ),
    Check(
        "admission server",
        ("python3", "-B", "scripts/verify_admission_server.py"),
        contains=("admission-server: passed", "endpoint: /validate", "cluster-access: none"),
    ),
    Check(
        "digest",
        ("python3", "-B", "bin/kube-actuary", "digest", "examples/apply-configmap.preflight.capsule.json"),
        contains=("sha256:",),
    ),
    Check(
        "render crd",
        (
            "python3",
            "-B",
            "bin/kube-actuary",
            "render-crd",
            "examples/apply-configmap.preflight.capsule.json",
            "--name",
            "apply-configmap",
            "--namespace",
            "default",
        ),
        contains=(
            "apiVersion: \"ops.kubeactuary.dev/v1alpha1\"",
            "kubeactuary.dev/capsule-digest",
            "status:",
            "phase: \"GateOpen\"",
            "type: \"EvidenceComplete\"",
            "type: \"RollbackReady\"",
        ),
    ),
    Check(
        "verified manifest gate opens",
        ("python3", "-B", "bin/kube-actuary", "gate", "examples/apply-configmap.preflight.capsule.json"),
        contains=("gate: open",),
    ),
    Check(
        "draft scale gate closes",
        ("python3", "-B", "bin/kube-actuary", "gate", "examples/scale-prod-deployment.capsule.json"),
        expected_returncode=1,
        contains=("gate: closed", "missing evidence"),
    ),
    Check(
        "example json parse",
        ("python3", "-B", "-m", "json.tool", "examples/apply-configmap.preflight.capsule.json"),
    ),
    Check(
        "schema json parse",
        ("python3", "-B", "-m", "json.tool", "schemas/operation-capsule.v0alpha1.schema.json"),
    ),
    Check(
        "yaml parse",
        (
            "ruby",
            "-e",
            'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"',
            ".github/workflows/ci.yml",
            "charts/kubeactuary/Chart.yaml",
            "charts/kubeactuary/values.yaml",
            "deploy/kustomize/base/kustomization.yaml",
            "deploy/kustomize/overlays/controller-namespace/kustomization.yaml",
            "deploy/kustomize/overlays/controller-cluster/kustomization.yaml",
            "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
            "deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml",
            "deploy/controller/namespace-scoped-rbac.yaml",
            "deploy/controller/cluster-scoped-rbac.yaml",
            "deploy/admission/validatingwebhookconfiguration.yaml",
            "examples/operationcapsule-scale.yaml",
            "examples/configmap-demo.yaml",
            "examples/configmap-demo.rollback.yaml",
        ),
        contains=("yaml ok",),
    ),
    Check("diff check", ("git", "diff", "--check")),
)


SUITES: dict[str, tuple[Check, ...]] = {
    "0.2.0": COMMON_CHECKS,
    "current": COMMON_CHECKS,
}


def run_check(check: Check, verbose: bool) -> bool:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        check.command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    combined = result.stdout + result.stderr
    ok = result.returncode == check.expected_returncode
    if ok and check.contains:
        ok = all(pattern in combined for pattern in check.contains)
    if ok and check.json_probe == "agent_help":
        ok = validate_agent_help_json(result.stdout)

    status = "PASS" if ok else "FAIL"
    print(f"{status} {check.name}")
    if verbose or not ok:
        print(f"  command: {' '.join(check.command)}")
        print(f"  expected returncode: {check.expected_returncode}")
        print(f"  actual returncode: {result.returncode}")
        if combined.strip():
            for line in combined.strip().splitlines()[:40]:
                print(f"  | {line}")
    return ok


def validate_agent_help_json(output: str) -> bool:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return False
    commands = payload.get("commands", [])
    compatibility = payload.get("compatibility", {})
    if payload.get("name") != "kube-actuary":
        return False
    if payload.get("schemaVersion") != "kube-actuary.help.v1":
        return False
    if compatibility.get("schemaVersion") != "kube-actuary.help.v1":
        return False
    if not commands:
        return False
    for field in compatibility.get("requiredTopLevelFields", []):
        if field not in payload:
            return False
    required_command_fields = compatibility.get("requiredCommandFields", [])
    if not required_command_fields:
        return False
    if any(field not in command for command in commands for field in required_command_fields):
        return False
    if any(command.get("clusterWrites") is not False for command in commands):
        return False
    validate_command = next((command for command in commands if command.get("name") == "validate"), None)
    if not validate_command or validate_command.get("clusterAccess") != "none":
        return False
    doctor_command = next((command for command in commands if command.get("name") == "doctor"), None)
    if not doctor_command or doctor_command.get("clusterAccess") != "kubectl version --client=true -o json":
        return False
    contract = payload.get("agentContract", {})
    return "the capsule spec.proposedCommand" in contract.get("neverExecutes", [])


def list_suites() -> None:
    for version, checks in sorted(SUITES.items()):
        print(f"{version}: {len(checks)} checks")
        for check in checks:
            print(f"  - {check.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run KubeActuary release verification suites.")
    parser.add_argument("--version", default="current", choices=sorted(SUITES))
    parser.add_argument("--list", action="store_true", help="list available suites and checks")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        list_suites()
        return 0

    checks = SUITES[args.version]
    print(f"Running KubeActuary release verification: {args.version}")
    failed = 0
    for check in checks:
        if not run_check(check, args.verbose):
            failed += 1
    if failed:
        print(f"verification: failed ({failed}/{len(checks)} failed)")
        return 1
    print(f"verification: passed ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
