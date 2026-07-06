#!/usr/bin/env python3
"""Run repeatable KubeActuary release verification suites."""

from __future__ import annotations

import argparse
import json
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
        "lightweight cluster smoke",
        ("python3", "-B", "scripts/verify_lightweight_cluster_smoke.py"),
        contains=(
            "lightweight-cluster-smoke: passed",
            "providers: kind, minikube, microk8s, k3s",
            "mode: offline-plan",
        ),
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
            "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
            "deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml",
            "deploy/controller/namespace-scoped-rbac.yaml",
            "deploy/controller/cluster-scoped-rbac.yaml",
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
    result = subprocess.run(
        check.command,
        cwd=ROOT,
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
