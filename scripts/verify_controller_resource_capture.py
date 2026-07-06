#!/usr/bin/env python3
"""Verify controller resource-budget capture stays read-only and auditable."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "scripts" / "capture_controller_resource_budget.py"
BUILDER = ROOT / "scripts" / "build_external_evidence.py"
README = ROOT / "README.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"


def run_capture(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CAPTURE), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_kubectl(path: Path, cpu: str, memory: str, exit_code: int = 0) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    executable = path / "kubectl"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['top', 'pod']:\n"
        f"    print('POD NAME CPU(cores) MEMORY(bytes)')\n"
        f"    print('controller-0 controller {cpu} {memory}')\n"
        f"    raise SystemExit({exit_code})\n"
        "raise SystemExit(2)\n"
    )
    executable.chmod(0o755)
    return executable


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        raw = tmpdir / "raw" / "kubectl-top.txt"
        evidence = tmpdir / "supplemental" / "resource-budget.json"
        kubectl = fake_kubectl(tmpdir, "12m", "41Mi")

        plan = run_capture("--output", str(raw))
        if plan.returncode != 0:
            errors.append(f"plan mode failed: {plan.stderr.strip() or plan.stdout.strip()}")
        if "controller-resource-capture: plan" not in plan.stdout:
            errors.append("plan mode must print plan status")
        if raw.exists():
            errors.append("plan mode must not create raw evidence files")

        captured = run_capture("--kubectl", str(kubectl), "--output", str(raw), "--run", "--format", "json")
        if captured.returncode != 0:
            errors.append(f"capture run failed: {captured.stderr.strip() or captured.stdout.strip()}")
            payload = {}
        else:
            payload = json.loads(captured.stdout)
        if payload.get("schemaVersion") != "kube-actuary.controller-resource-capture.v1":
            errors.append("capture schemaVersion mismatch")
        if payload.get("clusterWrites") != "disabled":
            errors.append("capture must record disabled cluster writes")
        if payload.get("mode") != "captured":
            errors.append(f"capture mode mismatch: {payload.get('mode')!r}")
        if payload.get("measurement", {}).get("schemaVersion") != "kube-actuary.controller-resource-measurement.v1":
            errors.append("capture must include structured measurement payload")
        if not raw.is_file() or "controller-0 controller 12m 41Mi" not in raw.read_text():
            errors.append("capture must write raw kubectl top output")

        built = subprocess.run(
            [
                sys.executable,
                "-B",
                str(BUILDER),
                "--kind",
                "controller-resource-budget",
                "--source",
                str(raw),
                "--output",
                str(evidence),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if built.returncode != 0 or not evidence.is_file():
            errors.append(f"supplemental evidence build failed: {built.stderr.strip() or built.stdout.strip()}")
        else:
            evidence_payload = json.loads(evidence.read_text())
            if evidence_payload.get("ok") is not True:
                errors.append("supplemental resource budget evidence must pass for good capture")
            if evidence_payload.get("source", {}).get("bytes") != raw.stat().st_size:
                errors.append("supplemental evidence must describe the captured raw file")

        high_raw = tmpdir / "raw" / "high-kubectl-top.txt"
        high_kubectl = fake_kubectl(tmpdir / "high", "70m", "90Mi")
        high = run_capture("--kubectl", str(high_kubectl), "--output", str(high_raw), "--run", "--format", "json")
        if high.returncode == 0:
            errors.append("capture must fail when the captured resource sample exceeds budget")
        if not high_raw.is_file():
            errors.append("failed budget capture should still preserve raw output")

    for snippet in ("capture_controller_resource_budget.py", "controller-resource-capture"):
        if snippet not in README.read_text():
            errors.append(f"README missing capture helper detail: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing capture helper detail: {snippet}")

    if errors:
        print("controller-resource-capture: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-resource-capture: passed")
    print("cluster-writes: disabled")
    print("raw-output: captured")
    print("supplemental: buildable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
