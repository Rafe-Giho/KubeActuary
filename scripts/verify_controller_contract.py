#!/usr/bin/env python3
"""Verify the low-overhead controller contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"
DOC = ROOT / "docs" / "controller.md"

FORBIDDEN_WATCH_TARGETS = ("pods", "deployments", "events", "nodes")


def run_controller(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CONTROLLER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def sample_capsule() -> dict:
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
            "evidence": [
                {"id": "intent", "ok": True, "summary": "reviewed", "actor": "reviewer", "attachedAt": "now"},
                {"id": "server-dry-run", "ok": True, "summary": "ok", "actor": "ci", "attachedAt": "now"},
                {"id": "rollback", "ok": True, "summary": "ok", "actor": "ci", "attachedAt": "now"},
            ],
            "rollback": {"required": True, "provided": True},
        },
    }


def main() -> int:
    errors: list[str] = []
    watch = run_controller("watch-command")
    if watch.returncode != 0:
        errors.append(f"watch-command failed: {watch.stderr.strip()}")
    command = watch.stdout.strip()
    expected = "kubectl get operationcapsules.ops.kubeactuary.dev -o json --watch --all-namespaces"
    if command != expected:
        errors.append(f"unexpected watch command: {command}")
    for target in FORBIDDEN_WATCH_TARGETS:
        if target in command:
            errors.append(f"watch command includes forbidden target: {target}")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "operationcapsule.json"
        path.write_text(json.dumps(sample_capsule()))
        reconcile = run_controller("reconcile", str(path), "--format", "patch")
    if reconcile.returncode != 0:
        errors.append(f"reconcile failed: {reconcile.stderr.strip()}")
    else:
        patch = json.loads(reconcile.stdout)
        if set(patch) != {"status"}:
            errors.append("reconcile patch must contain only status")
        status = patch.get("status", {})
        if status.get("gate") != "Open":
            errors.append("sample reconcile did not open gate")
        if not str(status.get("digest", "")).startswith("sha256:"):
            errors.append("sample reconcile missing digest")

    doc = DOC.read_text()
    for required in (
        "watch only",
        "operationcapsules.ops.kubeactuary.dev",
        "must not watch Pods",
        "must not run LLMs",
        "must not update `spec`",
    ):
        if required not in doc:
            errors.append(f"controller doc missing: {required}")

    if errors:
        print("controller-contract: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-contract: passed")
    print(f"watch: {command}")
    print("patch-scope: status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
