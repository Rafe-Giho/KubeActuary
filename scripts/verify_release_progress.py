#!/usr/bin/env python3
"""Verify versioned release progress report generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_release_progress.py"
README = ROOT / "README.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
sys.path.insert(0, str(ROOT))

from scripts.verify_live_evidence_schema import sample  # noqa: E402


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        evidence_dir.mkdir()
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = "kind"
        write_payload(evidence_dir / "kind.json", payload)

        json_result = run_generator("--format", "json")
        markdown_result = run_generator("--format", "markdown")
        with_evidence = run_generator("--format", "json", "--evidence-dir", str(evidence_dir))
        output = tmpdir / "progress.json"
        written = run_generator("--format", "json", "--output", str(output))
        output_written = output.is_file()

    if json_result.returncode != 0:
        errors.append(f"json progress failed: {json_result.stderr.strip() or json_result.stdout.strip()}")
        progress = {}
    else:
        progress = json.loads(json_result.stdout)
    if markdown_result.returncode != 0 or "# KubeActuary Release Progress" not in markdown_result.stdout:
        errors.append("markdown progress output must include heading")
    if with_evidence.returncode != 0:
        errors.append(f"evidence progress failed: {with_evidence.stderr.strip() or with_evidence.stdout.strip()}")
        evidence_progress = {}
    else:
        evidence_progress = json.loads(with_evidence.stdout)
    if written.returncode != 0 or not output_written:
        errors.append("progress generator must write requested output file")

    if progress.get("schemaVersion") != "kube-actuary.release-progress.v1":
        errors.append("release progress schemaVersion mismatch")
    if progress.get("releaseSuite", {}).get("checks") != 78:
        errors.append("release progress must report 78 release checks")
    if progress.get("summary", {}).get("verify") != 16:
        errors.append("release progress must report 16 VERIFY rows")
    if progress.get("summary", {}).get("doing") != 0 or progress.get("summary", {}).get("todo") != 0:
        errors.append("release progress must report zero DOING/TODO rows")
    versions = {group.get("version"): group for group in progress.get("versions", [])}
    for expected in ("Current Baseline", "0.2.0", "0.4.4", "0.9.0"):
        if expected not in versions:
            errors.append(f"release progress missing version group: {expected}")
    if versions.get("0.2.0", {}).get("summary", {}).get("done") != 3:
        errors.append("v0.2.0 group should remain fully DONE")
    if versions.get("0.4.4", {}).get("summary", {}).get("verify") != 1:
        errors.append("v0.4.4 group should keep lightweight smoke VERIFY")
    if progress.get("externalGatePlan", {}).get("verify") != 16:
        errors.append("progress report must include external gate summary")
    readiness = progress.get("liveValidationReadiness", {}).get("summary", {})
    if readiness.get("liveGates") != 7 or "toolReadyGates" not in readiness:
        errors.append("progress report must include live readiness summary")
    next_actions = progress.get("nextActions", {})
    if next_actions.get("summary", {}).get("total") != 16:
        errors.append("progress report must include one next action per external gate")
    for action in next_actions.get("actions", []):
        if action.get("status") not in {"tool-ready", "missing-tools"}:
            errors.append(f"invalid next action status: {action.get('status')!r}")
        if "missingTools" not in action:
            errors.append("next action must include missingTools")
    if not any(action.get("firstCommand") for action in next_actions.get("actions", [])):
        errors.append("next actions must include recommended commands")
    evidence_status = evidence_progress.get("evidenceStatus", {})
    if evidence_status.get("summary", {}).get("status") != "partial":
        errors.append("progress report must include partial evidence-dir status")
    if not evidence_status.get("nextCommands"):
        errors.append("partial evidence progress must include next commands")

    for snippet in ("generate_release_progress.py", "kube-actuary.release-progress.v1"):
        if snippet not in README.read_text():
            errors.append(f"README missing release progress detail: {snippet}")
    for snippet in ("Release progress", "verify_release_progress.py"):
        if snippet not in TASKBOARD.read_text():
            errors.append(f"taskboard missing release progress detail: {snippet}")

    if errors:
        print("release-progress: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-progress: passed")
    print("versions: ok")
    print("verify: 16")
    print("checks: 78")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
