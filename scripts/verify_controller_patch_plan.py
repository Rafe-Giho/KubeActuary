#!/usr/bin/env python3
"""Verify controller status patch planning stays status-only and non-executing."""

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


def sample_capsule(name: str, namespace: str) -> dict:
    return {
        "apiVersion": "ops.kubeactuary.dev/v1alpha1",
        "kind": "OperationCapsule",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "intent": "apply demo",
            "actor": {"type": "ai-agent", "name": "codex"},
            "proposedAction": {"verb": "manifest", "namespace": namespace},
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


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "operationcapsules.json"
        path.write_text(json.dumps({"items": [sample_capsule("demo-a", "team-a"), sample_capsule("demo-b", "team-b")]}))
        result = run_controller("patch-plan", str(path))
        commands = run_controller("patch-plan", str(path), "--format", "commands")

    if result.returncode != 0:
        errors.append(f"patch-plan failed: {result.stderr.strip()}")
        plan = {}
    else:
        plan = json.loads(result.stdout)

    if plan.get("writeExecution") != "disabled":
        errors.append("patch plan must keep write execution disabled")
    if plan.get("count") != 2:
        errors.append("patch plan must include two sample patches")
    for patch in plan.get("patches", []):
        command = patch.get("command", [])
        if WATCH_RESOURCE not in command:
            errors.append("patch command missing OperationCapsule resource")
        if "--subresource" not in command or "status" not in command:
            errors.append("patch command must target status subresource")
        if "apply" in command or "delete" in command:
            errors.append("patch command must not apply or delete")
        patch_body = patch.get("patch", {})
        if set(patch_body) != {"status"}:
            errors.append("patch body must contain only status")

    if commands.returncode != 0:
        errors.append(f"patch-plan --format commands failed: {commands.stderr.strip()}")
    elif "kubectl patch operationcapsules.ops.kubeactuary.dev" not in commands.stdout:
        errors.append("command output missing kubectl patch plan")

    doc = DOC.read_text()
    for snippet in ("patch-plan", "writeExecution", "disabled", "--subresource status", "does not execute"):
        if snippet not in doc:
            errors.append(f"controller doc missing patch-plan contract: {snippet}")

    if errors:
        print("controller-patch-plan: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-patch-plan: passed")
    print("patch-scope: status")
    print("write-execution: disabled")
    print("items: 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
