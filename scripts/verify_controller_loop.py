#!/usr/bin/env python3
"""Verify controller loop stays low-overhead and dry-run by default."""

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
        "metadata": {"name": "demo-loop", "namespace": "team-a"},
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
                "if sys.argv[1] == 'patch':",
                "    print('status dry-run ok')",
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
        result = run_controller(
            "loop",
            "--kubectl",
            str(kubectl),
            "--iterations",
            "2",
            "--interval-seconds",
            "0",
        )
        calls = json.loads(log_path.read_text()) if log_path.exists() else []

    if result.returncode != 0:
        errors.append(f"loop failed: {result.stderr.strip()}")
        report = {}
    else:
        report = json.loads(result.stdout)

    expected_get = ["get", WATCH_RESOURCE, "-o", "json", "--all-namespaces"]
    if len(calls) != 4:
        errors.append(f"expected four kubectl calls for two ticks, got {calls!r}")
    else:
        if calls[0] != expected_get or calls[2] != expected_get:
            errors.append(f"loop must read OperationCapsules once per tick: {calls!r}")
        for call in (calls[1], calls[3]):
            if call[0] != "patch":
                errors.append(f"loop status action must be kubectl patch: {call}")
            if WATCH_RESOURCE not in call:
                errors.append("loop patch missing OperationCapsule resource")
            if "--subresource" not in call or "status" not in call:
                errors.append("loop patch must target status subresource")
            if "--dry-run=server" not in call:
                errors.append("default loop patch must be server-side dry-run")
            if "apply" in call or "delete" in call:
                errors.append("loop must not apply or delete workload resources")

    if report.get("mode") != "server-dry-run-loop":
        errors.append("default loop report must be server-dry-run-loop")
    if report.get("writeExecution") != "disabled":
        errors.append("default loop must keep writeExecution disabled")
    if report.get("readExecution") != "kubectl-get":
        errors.append("loop must report kubectl-get read execution")
    if report.get("patchScope") != "status":
        errors.append("loop must report status patch scope")
    if report.get("iterations") != 2:
        errors.append("loop verifier must exercise two iterations")
    if report.get("failed") != 0:
        errors.append("fake loop should have no failed patches")

    doc = DOC.read_text()
    for snippet in ("loop", "--iterations", "--dry-run=server", "--execute", "verify_controller_loop.py"):
        if snippet not in doc:
            errors.append(f"controller doc missing loop contract: {snippet}")

    if errors:
        print("controller-loop: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-loop: passed")
    print("default-mode: server-dry-run")
    print("write-execution: disabled")
    print("iterations: 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
