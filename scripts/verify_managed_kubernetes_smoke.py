#!/usr/bin/env python3
"""Verify managed Kubernetes smoke harness without cloud or cluster access."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "run_managed_kubernetes_smoke.py"
DOC = ROOT / "docs" / "managed-kubernetes-smoke.md"
PROVIDERS = ("eks", "gke", "aks")


def run_plan(provider: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SMOKE), "--provider", provider],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_tool(tmpdir: Path, name: str, log_name: str, body: str) -> tuple[Path, Path]:
    log_path = tmpdir / log_name
    tool = tmpdir / name
    tool.write_text(
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
                f"print({body!r})",
            ]
        )
    )
    tool.chmod(0o755)
    return tool, log_path


def run_fake_smoke(provider: str, tmpdir: Path) -> tuple[subprocess.CompletedProcess[str], dict, list[list[str]], list[list[str]]]:
    kubectl, kubectl_log = fake_tool(tmpdir, "kubectl", f"{provider}-kubectl.json", "kubectl ok")
    provider_cli, provider_log = fake_tool(tmpdir, "provider-cli", f"{provider}-provider.json", f"{provider} cli ok")
    output = tmpdir / f"{provider}-managed-smoke.json"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SMOKE),
            "--provider",
            provider,
            "--kubectl",
            str(kubectl),
            "--provider-cli",
            str(provider_cli),
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
    kubectl_calls = json.loads(kubectl_log.read_text()) if kubectl_log.exists() else []
    provider_calls = json.loads(provider_log.read_text()) if provider_log.exists() else []
    return result, report, kubectl_calls, provider_calls


def main() -> int:
    errors: list[str] = []
    for provider in PROVIDERS:
        plan = run_plan(provider)
        if plan.returncode != 0:
            errors.append(f"{provider}: plan failed: {plan.stderr.strip()}")
            continue
        for required in (
            "managed-kubernetes-smoke: plan",
            f"provider: {provider}",
            "kubectl version --client=true -o json",
            "kubectl apply --dry-run=server -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
            "kubectl explain operationcapsules --api-version=ops.kubeactuary.dev/v1alpha1",
            "kubectl auth can-i patch operationcapsules/status.ops.kubeactuary.dev",
        ):
            if required not in plan.stdout:
                errors.append(f"{provider}: plan missing {required}")
        for forbidden in ("kubectl apply -f", "kubectl delete", "kubectl create", "update-kubeconfig", "get-credentials"):
            if forbidden in plan.stdout:
                errors.append(f"{provider}: plan includes forbidden operation {forbidden}")

        with tempfile.TemporaryDirectory() as tmp:
            result, report, kubectl_calls, provider_calls = run_fake_smoke(provider, Path(tmp))
        if result.returncode != 0:
            errors.append(f"{provider}: fake run failed: {result.stderr.strip()}")
        if "managed-kubernetes-smoke: passed" not in result.stdout:
            errors.append(f"{provider}: fake run must pass")
        if report.get("schemaVersion") != "kube-actuary.managed-kubernetes-smoke.v1":
            errors.append(f"{provider}: evidence schema mismatch")
        if report.get("provider") != provider:
            errors.append(f"{provider}: report provider mismatch")
        if report.get("clusterWrites") != "server-side-dry-run-only":
            errors.append(f"{provider}: report must keep writes server-side dry-run only")
        if report.get("cloudApi") != "version-command-only":
            errors.append(f"{provider}: report must keep cloud API use version-only")
        if report.get("summary", {}).get("total") != 7 or report.get("summary", {}).get("failed") != 0:
            errors.append(f"{provider}: report must include seven successful commands")
        if len(provider_calls) != 1:
            errors.append(f"{provider}: provider CLI should run once")
        for call in kubectl_calls:
            if "delete" in call or "create" in call:
                errors.append(f"{provider}: forbidden kubectl operation: {call}")
            if call[:1] == ["apply"] and "--dry-run=server" not in call:
                errors.append(f"{provider}: apply must be server-side dry-run: {call}")

    doc = DOC.read_text() if DOC.is_file() else ""
    for required in (
        "EKS",
        "GKE",
        "AKS",
        "scripts/run_managed_kubernetes_smoke.py",
        "kube-actuary.managed-kubernetes-smoke.v1",
        "server-side-dry-run-only",
        "version-command-only",
    ):
        if required not in doc:
            errors.append(f"managed smoke doc missing: {required}")

    if errors:
        print("managed-kubernetes-smoke: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("managed-kubernetes-smoke: passed")
    print("providers: eks, gke, aks")
    print("mode: offline-plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
