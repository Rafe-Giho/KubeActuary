#!/usr/bin/env python3
"""Verify optional admission webhook prototype manifest."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "deploy" / "admission" / "validatingwebhookconfiguration.yaml"
DOC = ROOT / "docs" / "admission.md"
SMOKE_DOC = ROOT / "docs" / "admission-kind-smoke.md"
SMOKE = ROOT / "scripts" / "run_admission_kind_smoke.py"


def run_fake_smoke(tmpdir: Path) -> tuple[subprocess.CompletedProcess[str], dict, list[list[str]]]:
    output = tmpdir / "admission-kind-smoke.json"
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
                "elif args[:2] == ['apply', '--dry-run=server']:",
                "    print('server-side dry-run ok')",
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
            "-B",
            str(SMOKE),
            "--kubectl",
            str(kubectl),
            "--python",
            sys.executable,
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
    text = MANIFEST.read_text() if MANIFEST.is_file() else ""
    doc = DOC.read_text() if DOC.is_file() else ""

    required = (
        "apiVersion: admissionregistration.k8s.io/v1",
        "kind: ValidatingWebhookConfiguration",
        "failurePolicy: Ignore",
        "sideEffects: None",
        "timeoutSeconds: 2",
        "kubeactuary.dev/admission: enabled",
        "operations:",
        "- CREATE",
        "- UPDATE",
        "- PATCH",
        "- DELETE",
        "service:",
        "path: /validate",
    )
    for value in required:
        if value not in text:
            errors.append(f"manifest missing: {value}")

    forbidden = ("failurePolicy: Fail", "reinvocationPolicy", "kubectl apply")
    for value in forbidden:
        if value in text:
            errors.append(f"manifest must not include: {value}")

    for value in ("failurePolicy: Ignore", "namespace opt-in", "kind smoke remains"):
        if value not in doc:
            errors.append(f"admission docs missing: {value}")

    with tempfile.TemporaryDirectory() as tmp:
        result, report, calls = run_fake_smoke(Path(tmp))
    if result.returncode != 0:
        errors.append(f"admission kind smoke fake run failed: {result.stderr.strip()}")
    if "admission-kind-smoke: passed" not in result.stdout:
        errors.append("admission kind smoke fake run must pass")
    if report.get("schemaVersion") != "kube-actuary.admission-kind-smoke.v1":
        errors.append("admission kind smoke evidence schema mismatch")
    if report.get("clusterWrites") != "server-side-dry-run-only":
        errors.append("admission kind smoke must report server-side dry-run writes")
    if report.get("localServer") != "loopback-only":
        errors.append("admission kind smoke must keep server checks loopback-only")
    summary = report.get("summary", {})
    if summary.get("total") != 5 or summary.get("failed") != 0:
        errors.append("admission kind smoke must record five successful commands")
    for record in report.get("commands", []):
        if record.get("ok") is not True or "stdout" not in record or "stderr" not in record:
            errors.append("admission kind smoke records must include ok/stdout/stderr")
    for call in calls:
        if "delete" in call or "create" in call or "patch" in call:
            errors.append(f"admission kind smoke must not execute mutating kubectl call: {call}")
        if call[:1] == ["apply"] and "--dry-run=server" not in call:
            errors.append(f"admission kind smoke apply must be server-side dry-run: {call}")

    smoke_doc = SMOKE_DOC.read_text() if SMOKE_DOC.is_file() else ""
    for value in (
        "scripts/run_admission_kind_smoke.py",
        "kube-actuary.admission-kind-smoke.v1",
        "server-side-dry-run-only",
        "does not require kind to be installed",
    ):
        if value not in smoke_doc:
            errors.append(f"admission kind smoke docs missing: {value}")

    kind = shutil.which("kind")
    if kind is None:
        live_status = "kind-unavailable"
    else:
        live_status = "kind-available"

    if errors:
        print("admission-webhook: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-webhook: passed")
    print("failurePolicy: Ignore")
    print("evidence-schema: kube-actuary.admission-kind-smoke.v1")
    print(f"kind-smoke: {live_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
