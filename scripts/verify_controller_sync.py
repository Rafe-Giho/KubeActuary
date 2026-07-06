#!/usr/bin/env python3
"""Verify controller sync reads OperationCapsules and emits a non-writing plan."""

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
        "metadata": {"name": "demo-sync", "namespace": "team-a"},
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
        [sys.executable, "-B", str(CONTROLLER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_kubectl(tmpdir: Path, payload: dict) -> tuple[Path, Path]:
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
    return kubectl, log_path


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        kubectl, log_path = fake_kubectl(tmpdir, {"items": [sample_capsule()]})
        result = run_controller("sync", "--kubectl", str(kubectl))
        namespaced = run_controller("sync", "--kubectl", str(kubectl), "--namespace", "team-a")
        calls = json.loads(log_path.read_text()) if log_path.exists() else []

    if result.returncode != 0:
        errors.append(f"sync failed: {result.stderr.strip()}")
        plan = {}
    else:
        plan = json.loads(result.stdout)

    if namespaced.returncode != 0:
        errors.append(f"namespaced sync failed: {namespaced.stderr.strip()}")

    expected_calls = [
        ["get", WATCH_RESOURCE, "-o", "json", "--all-namespaces"],
        ["get", WATCH_RESOURCE, "-o", "json", "-n", "team-a"],
    ]
    if calls != expected_calls:
        errors.append(f"sync must execute only expected get calls: {calls!r}")
    for call in calls:
        for forbidden in ("patch", "apply", "delete"):
            if forbidden in call:
                errors.append(f"sync executed forbidden kubectl verb: {forbidden}")

    if plan.get("readExecution") != "kubectl-get":
        errors.append("sync must report kubectl-get read execution")
    if plan.get("readCommand") != [str(kubectl), *expected_calls[0]]:
        errors.append("sync must report the exact read command")
    if plan.get("writeExecution") != "disabled":
        errors.append("sync must keep write execution disabled")
    if plan.get("count") != 1:
        errors.append("sync must emit one status patch plan")
    for patch in plan.get("patches", []):
        if set(patch.get("patch", {})) != {"status"}:
            errors.append("sync patch body must contain only status")
        command = patch.get("command", [])
        if "--subresource" not in command or "status" not in command:
            errors.append("sync patch plan must target the status subresource")

    doc = DOC.read_text()
    for snippet in ("sync", "read-only", "writeExecution", "disabled", "verify_controller_sync.py"):
        if snippet not in doc:
            errors.append(f"controller doc missing sync contract: {snippet}")

    if errors:
        print("controller-sync: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-sync: passed")
    print("read: operationcapsules")
    print("write-execution: disabled")
    print("executed-writes: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
