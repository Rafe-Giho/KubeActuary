#!/usr/bin/env python3
"""Verify local CI and Codex agent runbook examples."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOKS = (
    ROOT / "examples" / "agent-local-ci.runbook.md",
    ROOT / "examples" / "agent-codex-workflow.runbook.md",
)
REQUIRED = {
    "agent-local-ci.runbook.md": (
        "help agents --format json",
        "verify_agent_help_contract.py",
        "validate examples/apply-configmap.preflight.capsule.json",
        "gate examples/apply-configmap.preflight.capsule.json",
    ),
    "agent-codex-workflow.runbook.md": (
        "scripts/kube_actuary_mcp_server.py",
        "draft_operation_capsule",
        "inspect_operation_capsule",
        "attach_operation_evidence",
        "verify_operation_capsule",
        "gate_operation_capsule",
        "execute_approved_capsule` disabled",
    ),
}


def run_check(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    for path in RUNBOOKS:
        if not path.is_file():
            errors.append(f"missing runbook: {path.relative_to(ROOT)}")
            continue
        text = path.read_text()
        for required in REQUIRED[path.name]:
            if required not in text:
                errors.append(f"{path.name} missing: {required}")
        if "kubectl apply" in text or "kubectl delete" in text:
            errors.append(f"{path.name} must not instruct direct Kubernetes writes")

    for command in (
        [sys.executable, "-B", "scripts/verify_agent_help_contract.py"],
        [sys.executable, "-B", "scripts/verify_mcp_contract.py"],
    ):
        result = run_check(command)
        if result.returncode != 0:
            errors.append(f"{' '.join(command)} failed: {result.stderr.strip()}")

    if errors:
        print("agent-examples: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("agent-examples: passed")
    print("runbooks: 2")
    print("writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
