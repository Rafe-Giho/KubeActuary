#!/usr/bin/env python3
"""Verify the Helm chart contract without requiring Helm."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "charts" / "kubeactuary"
VERSION = (ROOT / "VERSION").read_text().strip()
CRD = ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
CHART_CRD = CHART / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
VALUES = CHART / "values.yaml"
TEMPLATE = CHART / "templates" / "controller-rbac.yaml"
DEPLOYMENT_TEMPLATE = CHART / "templates" / "controller-deployment.yaml"
SMOKE = ROOT / "scripts" / "run_helm_smoke.py"
DOC = ROOT / "docs" / "helm-smoke.md"


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def run_fake_smoke(tmpdir: Path) -> tuple[subprocess.CompletedProcess[str], dict, dict[str, list[list[str]]]]:
    output = tmpdir / "helm-smoke.json"
    helm_log = tmpdir / "helm-calls.json"
    kubectl_log = tmpdir / "kubectl-calls.json"
    helm = tmpdir / "helm"
    kubectl = tmpdir / "kubectl"
    helm.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "from pathlib import Path",
                f"log_path = Path({str(helm_log)!r})",
                "calls = json.loads(log_path.read_text()) if log_path.exists() else []",
                "calls.append(sys.argv[1:])",
                "log_path.write_text(json.dumps(calls))",
                "args = sys.argv[1:]",
                "if args[:1] == ['template']:",
                "    print('apiVersion: v1\\nkind: List')",
                "elif args[:1] == ['install'] and '--dry-run' in args:",
                "    print('helm dry-run ok')",
                "else:",
                "    print('unexpected helm call', file=sys.stderr)",
                "    raise SystemExit(9)",
            ]
        )
    )
    kubectl.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "from pathlib import Path",
                f"log_path = Path({str(kubectl_log)!r})",
                "calls = json.loads(log_path.read_text()) if log_path.exists() else []",
                "calls.append(sys.argv[1:])",
                "log_path.write_text(json.dumps(calls))",
                "args = sys.argv[1:]",
                "if args[:2] == ['apply', '--dry-run=server']:",
                "    print('server-side dry-run ok')",
                "else:",
                "    print('unexpected kubectl call', file=sys.stderr)",
                "    raise SystemExit(9)",
            ]
        )
    )
    helm.chmod(0o755)
    kubectl.chmod(0o755)
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SMOKE),
            "--helm",
            str(helm),
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
    calls = {
        "helm": json.loads(helm_log.read_text()) if helm_log.exists() else [],
        "kubectl": json.loads(kubectl_log.read_text()) if kubectl_log.exists() else [],
    }
    return result, report, calls


def main() -> int:
    errors: list[str] = []
    chart_yaml = (CHART / "Chart.yaml").read_text()
    values = VALUES.read_text()
    template = TEMPLATE.read_text()
    deployment_template = DEPLOYMENT_TEMPLATE.read_text()

    require("apiVersion: v2" in chart_yaml, "Chart.yaml must use Helm v2 schema", errors)
    require("name: kubeactuary" in chart_yaml, "Chart.yaml name mismatch", errors)
    require(f"version: {VERSION}" in chart_yaml, "Chart.yaml version must match VERSION", errors)
    require(f'appVersion: "{VERSION}"' in chart_yaml, "Chart.yaml appVersion must match VERSION", errors)
    require(CHART_CRD.read_text() == CRD.read_text(), "chart CRD must match deploy CRD", errors)

    require("enabled: false" in values, "controller must be disabled by default", errors)
    require("scope: namespace" in values, "namespace-scoped RBAC must be default", errors)
    require("repository: ghcr.io/kubeactuary/kubeactuary-controller" in values, "controller image repository missing", errors)
    require("cpu: 10m" in values and "memory: 64Mi" in values, "controller resource budget missing", errors)

    for required in (
        "kind: ServiceAccount",
        "kind: Role",
        "kind: RoleBinding",
        "kind: ClusterRole",
        "kind: ClusterRoleBinding",
        'resources: ["operationcapsules"]',
        'resources: ["operationcapsules/status"]',
        'verbs: ["get", "list", "watch"]',
        'verbs: ["get", "patch", "update"]',
    ):
        require(required in template, f"controller RBAC template missing: {required}", errors)
    for forbidden in ('resources: ["*"]', 'apiGroups: ["*"]', 'verbs: ["*"]', "kind: Deployment"):
        require(forbidden not in template, f"controller RBAC template contains forbidden field: {forbidden}", errors)
    for required in (
        "kind: Deployment",
        "automountServiceAccountToken: false",
        "- serve",
        "/healthz",
        "/readyz",
        "readOnlyRootFilesystem: true",
    ):
        require(required in deployment_template, f"controller deployment template missing: {required}", errors)

    helm = shutil.which("helm")
    helm_status = "not-found"
    if helm:
        result = subprocess.run(
            [helm, "template", "kubeactuary", str(CHART), "--set", "controller.enabled=true"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        helm_status = "passed" if result.returncode == 0 else "failed"
        if result.returncode != 0:
            errors.append(f"helm template failed: {result.stderr.strip()}")

    with tempfile.TemporaryDirectory() as tmp:
        result, report, calls = run_fake_smoke(Path(tmp))
    require(result.returncode == 0, f"helm smoke fake run failed: {result.stderr.strip()}", errors)
    require("helm-smoke: passed" in result.stdout, "helm smoke fake run must pass", errors)
    require(report.get("schemaVersion") == "kube-actuary.helm-smoke.v1", "helm smoke evidence schema mismatch", errors)
    require(report.get("clusterWrites") == "dry-run-only", "helm smoke must report dry-run-only writes", errors)
    require(report.get("summary", {}).get("total") == 4, "helm smoke must record four commands", errors)
    require(report.get("summary", {}).get("failed") == 0, "helm smoke fake run must have no failed commands", errors)
    for record in report.get("commands", []):
        require(record.get("ok") is True, "helm smoke command record must be ok", errors)
        require("stdout" in record and "stderr" in record, "helm smoke command record must include raw output", errors)
    helm_calls = calls["helm"]
    kubectl_calls = calls["kubectl"]
    require(len(helm_calls) == 3, "helm smoke must call Helm three times", errors)
    require(len(kubectl_calls) == 1, "helm smoke must call kubectl once", errors)
    for call in helm_calls:
        require("delete" not in call and "upgrade" not in call, f"helm smoke must not execute forbidden Helm verb: {call}", errors)
        if call[:1] == ["install"]:
            require("--dry-run" in call, "helm install smoke must be dry-run", errors)
    for call in kubectl_calls:
        require(call[:2] == ["apply", "--dry-run=server"], "kubectl Helm smoke must be server-side dry-run", errors)

    doc = DOC.read_text()
    for required in (
        "scripts/run_helm_smoke.py",
        "--run --output",
        "kube-actuary.helm-smoke.v1",
        "dry-run-only",
        "does not require Helm to be installed",
    ):
        require(required in doc, f"Helm smoke doc missing: {required}", errors)

    if errors:
        print("helm-chart: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("helm-chart: passed")
    print("crd: included")
    print("controller: optional")
    print(f"helm-template: {helm_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
