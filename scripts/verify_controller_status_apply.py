#!/usr/bin/env python3
"""Verify controller status apply stays dry-run by default and status-only."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"
DOC = ROOT / "docs" / "controller.md"
WATCH_RESOURCE = "operationcapsules.ops.kubeactuary.dev"


def sample_capsule() -> dict:
    return {
        "apiVersion": "ops.kubeactuary.dev/v1alpha1",
        "kind": "OperationCapsule",
        "metadata": {"name": "demo-apply", "namespace": "team-a"},
        "spec": {
            "intent": "apply demo",
            "actor": {"type": "ai-agent", "name": "codex"},
            "proposedAction": {"verb": "manifest", "namespace": "team-a"},
            "risk": {"level": "medium", "reasons": ["cluster state may be modified"]},
            "requiredEvidence": ["intent"],
            "evidence": [{"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"}],
            "rollback": {"required": False, "provided": False},
        },
    }


def run_controller(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTROLLER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_kubectl(tmpdir: Path) -> tuple[Path, Path]:
    log_path = tmpdir / "kubectl-calls.json"
    kubectl = tmpdir / "kubectl"
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
    return kubectl, log_path


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        kubectl, log_path = fake_kubectl(tmpdir)
        capsule = tmpdir / "operationcapsule.json"
        capsule.write_text(json.dumps(sample_capsule()))
        dry_run = run_controller("apply-status", str(capsule), "--kubectl", str(kubectl))
        execute = run_controller("apply-status", str(capsule), "--kubectl", str(kubectl), "--execute")
        calls = json.loads(log_path.read_text()) if log_path.exists() else []

    if dry_run.returncode != 0:
        errors.append(f"apply-status dry-run failed: {dry_run.stderr.strip()}")
        report = {}
    else:
        report = json.loads(dry_run.stdout)
    if execute.returncode != 0:
        errors.append(f"apply-status execute fake run failed: {execute.stderr.strip()}")

    if len(calls) != 2:
        errors.append(f"expected two kubectl patch calls, got {calls!r}")
    else:
        dry_call, execute_call = calls
        if "--dry-run=server" not in dry_call:
            errors.append("default apply-status call must include --dry-run=server")
        if "--dry-run=server" in execute_call:
            errors.append("--execute apply-status call must not include dry-run")
        for call in calls:
            if call[0] != "patch":
                errors.append(f"apply-status must call kubectl patch only: {call}")
            if WATCH_RESOURCE not in call:
                errors.append("apply-status patch missing OperationCapsule resource")
            if "--subresource" not in call or "status" not in call:
                errors.append("apply-status patch must target status subresource")
            if "apply" in call or "delete" in call:
                errors.append("apply-status must not apply or delete")

    if report.get("mode") != "server-dry-run":
        errors.append("default apply-status report must be server-dry-run")
    if report.get("writeExecution") != "disabled":
        errors.append("default apply-status must keep writeExecution disabled")
    if report.get("patchScope") != "status":
        errors.append("apply-status report must be status scoped")
    if report.get("failed") != 0:
        errors.append("fake dry-run should have no failed patches")

    doc = DOC.read_text()
    for snippet in ("apply-status", "--dry-run=server", "--execute", "status-only", "verify_controller_status_apply.py"):
        if snippet not in doc:
            errors.append(f"controller doc missing status apply contract: {snippet}")

    if errors:
        print("controller-status-apply: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-status-apply: passed")
    print("default-mode: server-dry-run")
    print("patch-scope: status")
    print("write-execution: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
