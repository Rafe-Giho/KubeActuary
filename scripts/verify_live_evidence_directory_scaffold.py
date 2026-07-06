#!/usr/bin/env python3
"""Verify live evidence directory scaffold generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts" / "prepare_live_evidence_directory.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
PREPARE_TOOL = "prepare_live_evidence_directory.py"
VERIFY_TOOL = "verify_live_evidence_directory_scaffold.py"


def run_prepare(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PREPARE), str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        evidence_dir = Path(tmp) / "evidence"
        first = run_prepare(evidence_dir)
        second = run_prepare(evidence_dir)
        queue_json = evidence_dir / ".kubeactuary" / "live-validation-queue.json"
        queue_md = evidence_dir / ".kubeactuary" / "live-validation-queue.md"
        readme = evidence_dir / "README.md"
        expected_dirs = [evidence_dir / name for name in ("reports", "raw", "supplemental", ".kubeactuary")]
        queue = json.loads(queue_json.read_text()) if queue_json.is_file() else {}

        for name, result in (("first", first), ("second", second)):
            if result.returncode != 0:
                errors.append(f"{name} scaffold failed: {result.stderr.strip() or result.stdout.strip()}")
        if "live-evidence-directory: prepared" not in second.stdout:
            errors.append("scaffold must report prepared status")
        if "cluster-writes: disabled" not in second.stdout:
            errors.append("scaffold must report disabled writes")
        for path in expected_dirs:
            if not path.is_dir():
                errors.append(f"scaffold missing directory: {path.name}")
        for path in (queue_json, queue_md, readme):
            if not path.is_file():
                errors.append(f"scaffold missing file: {path.name}")
        if queue.get("schemaVersion") != "kube-actuary.live-validation-queue.v1":
            errors.append("scaffold queue schemaVersion mismatch")
        if queue.get("summary", {}).get("total") != 16:
            errors.append("scaffold queue must include 16 items")
        if queue.get("evidenceDir") != str(evidence_dir):
            errors.append("scaffold queue must record evidence directory")
        resolved = "\n".join(
            command
            for item in queue.get("items", [])
            for command in item.get("resolvedCommands", [])
        )
        if str(evidence_dir / "reports") not in resolved:
            errors.append("scaffold queue must resolve report paths under reports/")
        if str(evidence_dir / "supplemental") not in resolved:
            errors.append("scaffold queue must resolve supplemental paths")
        if "cluster-writes: `disabled`" not in readme.read_text():
            errors.append("scaffold README must document disabled writes")

    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        text = path.read_text()
        for snippet in (PREPARE_TOOL, VERIFY_TOOL):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing scaffold detail: {snippet}")

    if errors:
        print("live-evidence-directory-scaffold: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-evidence-directory-scaffold: passed")
    print("directories: 4")
    print("queue-items: 16")
    print("cluster-writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
