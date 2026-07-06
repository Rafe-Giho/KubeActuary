#!/usr/bin/env python3
"""Verify the lightweight cluster smoke harness without requiring clusters."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "run_lightweight_cluster_smoke.py"
DOC = ROOT / "docs" / "lightweight-cluster-smoke.md"
PROVIDERS = ("kind", "minikube", "microk8s", "k3s")


def run_plan(provider: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE), "--provider", provider],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_fake_smoke(tmpdir: Path) -> tuple[subprocess.CompletedProcess[str], dict, list[list[str]]]:
    output = tmpdir / "evidence.json"
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
                "args = sys.argv[1:]",
                "if args[:2] == ['version', '--client=true']:",
                "    print('{\"clientVersion\":{\"gitVersion\":\"v1.32.2\"}}')",
                "elif args[:1] == ['cluster-info']:",
                "    print('Kubernetes control plane is running')",
                "elif args[:2] == ['apply', '--dry-run=server']:",
                "    print('server-side dry-run ok')",
                "elif args[:3] == ['auth', 'can-i', 'get'] or args[:3] == ['auth', 'can-i', 'watch']:",
                "    print('yes')",
                "elif args[:3] == ['auth', 'can-i', 'patch']:",
                "    print('yes')",
                "elif args[:2] == ['top', 'pod']:",
                "    print('POD CONTAINER CPU MEMORY')",
                "else:",
                "    print('unexpected kubectl call', file=sys.stderr)",
                "    raise SystemExit(9)",
            ]
        )
    )
    kubectl.chmod(0o755)
    result = subprocess.run(
        [
            sys.executable,
            str(SMOKE),
            "--provider",
            "kind",
            "--kubectl",
            str(kubectl),
            "--run",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    report = json.loads(output.read_text()) if output.exists() else {}
    calls = json.loads(log_path.read_text()) if log_path.exists() else []
    return result, report, calls


def main() -> int:
    errors: list[str] = []
    for provider in PROVIDERS:
        result = run_plan(provider)
        output = result.stdout
        if result.returncode != 0:
            errors.append(f"{provider}: plan failed: {result.stderr.strip()}")
            continue
        for required in (
            "lightweight-cluster-smoke: plan",
            f"provider: {provider}",
            "kubectl apply --dry-run=server -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
            "kubectl apply --dry-run=server -f deploy/controller/namespace-scoped-rbac.yaml",
            "kubectl apply --dry-run=server -f deploy/controller/cluster-scoped-rbac.yaml",
            "kubectl auth can-i get operationcapsules.ops.kubeactuary.dev --all-namespaces",
            "kubectl top pod -n kubeactuary-system",
        ):
            if required not in output:
                errors.append(f"{provider}: plan missing {required}")
        for forbidden in ("kubectl apply -f", "kubectl delete", "kubectl create deployment", " pods --all-namespaces"):
            if forbidden in output:
                errors.append(f"{provider}: plan includes forbidden operation {forbidden}")

    with tempfile.TemporaryDirectory() as tmp:
        result, report, calls = run_fake_smoke(Path(tmp))
    if result.returncode != 0:
        errors.append(f"fake run failed: {result.stderr.strip()}")
    if "lightweight-cluster-smoke: passed" not in result.stdout:
        errors.append("fake run missing passed output")
    if report.get("schemaVersion") != "kube-actuary.lightweight-smoke.v1":
        errors.append("evidence report schema mismatch")
    if report.get("mode") != "run" or report.get("provider") != "kind":
        errors.append("evidence report must identify run mode and provider")
    if report.get("clusterWrites") != "server-side-dry-run-only":
        errors.append("evidence report must keep cluster writes dry-run only")
    summary = report.get("summary", {})
    if summary.get("total") != 9 or summary.get("failed") != 0:
        errors.append("evidence report must include all successful commands")
    for record in report.get("commands", []):
        if record.get("ok") is not True or "stdout" not in record or "stderr" not in record:
            errors.append("evidence command records must include ok/stdout/stderr")
    for call in calls:
        if "delete" in call or "create" in call:
            errors.append(f"fake run executed forbidden call: {call}")
        if call[:1] == ["apply"] and "--dry-run=server" not in call:
            errors.append(f"fake run apply call must be server-side dry-run: {call}")

    doc = DOC.read_text()
    for required in (
        "kind",
        "minikube",
        "MicroK8s",
        "k3s",
        "server-side dry-run",
        "scripts/run_lightweight_cluster_smoke.py",
        "--output",
        "kube-actuary.lightweight-smoke.v1",
    ):
        if required not in doc:
            errors.append(f"smoke doc missing: {required}")

    if errors:
        print("lightweight-cluster-smoke: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("lightweight-cluster-smoke: passed")
    print("providers: kind, minikube, microk8s, k3s")
    print("mode: offline-plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
