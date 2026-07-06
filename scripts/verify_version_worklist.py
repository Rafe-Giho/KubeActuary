#!/usr/bin/env python3
"""Verify version worklist generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_version_worklist.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
WORKLIST_TOOL = "generate_version_worklist.py"
VERIFY_TOOL = "verify_version_worklist.py"
SCHEMA = "kube-actuary.version-worklist.v1"


def run_generator(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def parse_worklist(label: str, result: subprocess.CompletedProcess[str], errors: list[str]) -> dict:
    if result.returncode != 0:
        errors.append(f"{label} failed: {result.stderr.strip() or result.stdout.strip()}")
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must parse: {exc}")
        return {}


def fake_all_tools_env(path: Path, cluster_ok: bool) -> dict[str, str]:
    path.mkdir()
    for tool in ("kind", "minikube", "microk8s", "k3s", "helm", "kubectl-krew", "aws", "gcloud", "az"):
        executable = path / tool
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    kubectl = path / "kubectl"
    cluster_exit = 0 if cluster_ok else 1
    kubectl.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['version']:\n"
        "    print('Client Version: fake')\n"
        "    raise SystemExit(0)\n"
        "if args[:1] == ['cluster-info']:\n"
        f"    raise SystemExit({cluster_exit})\n"
        "raise SystemExit(0)\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def main() -> int:
    errors: list[str] = []
    json_result = run_generator("--format", "json")
    markdown_result = run_generator("--format", "markdown")
    single_version_result = run_generator("--format", "json", "--version", "0.4.3")
    multi_version_result = run_generator("--format", "json", "--version", "0.3.3", "--version", "0.4.3")
    open_only_result = run_generator("--format", "json", "--open-only")
    invalid_version_result = run_generator("--version", "9.9.9")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        output = tmpdir / "worklist.json"
        written = run_generator("--output", str(output))
        output_written = output.is_file()
        probe_env = fake_all_tools_env(tmpdir / "tools", cluster_ok=False)
        probe_result = run_generator("--format", "json", "--open-only", "--probe-environment", env=probe_env)

    worklist = parse_worklist("json worklist", json_result, errors)
    single_version = parse_worklist("single-version worklist", single_version_result, errors)
    multi_version = parse_worklist("multi-version worklist", multi_version_result, errors)
    open_only = parse_worklist("open-only worklist", open_only_result, errors)
    probe_worklist = parse_worklist("probe worklist", probe_result, errors)
    if markdown_result.returncode != 0:
        errors.append(f"markdown worklist failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    if "# KubeActuary Version Worklist" not in markdown_result.stdout:
        errors.append("markdown worklist missing heading")
    if written.returncode != 0 or not output_written:
        errors.append("worklist generator must write requested output file")
    invalid_text = invalid_version_result.stdout + invalid_version_result.stderr
    if invalid_version_result.returncode == 0:
        errors.append("unknown version filter must fail")
    if "unknown version: 9.9.9" not in invalid_text:
        errors.append("unknown version filter must explain the missing version")

    summary = worklist.get("summary", {})
    versions = {version.get("version"): version for version in worklist.get("versions", []) if isinstance(version, dict)}
    if worklist.get("schemaVersion") != SCHEMA:
        errors.append("version worklist schemaVersion mismatch")
    if summary.get("openItems") != 16:
        errors.append(f"expected 16 open items, got {summary.get('openItems')!r}")
    if summary.get("captureReady") != 4:
        errors.append(f"expected 4 capture-ready items, got {summary.get('captureReady')!r}")
    if summary.get("blockedByTools") != 12:
        errors.append(f"expected 12 tool-blocked items, got {summary.get('blockedByTools')!r}")
    if summary.get("blockedByEnvironment") != 0:
        errors.append("default version worklist must not probe environment blockers")
    for expected in ("Current Baseline", "0.2.0", "0.4.4", "0.9.0"):
        if expected not in versions:
            errors.append(f"version worklist missing version: {expected}")
    if versions.get("0.2.0", {}).get("status") != "complete":
        errors.append("0.2.0 worklist should be complete")
    if versions.get("Current Baseline", {}).get("status") != "capture-ready":
        errors.append("current baseline should include capture-ready work")
    if versions.get("0.4.4", {}).get("status") != "missing-tools":
        errors.append("0.4.4 should remain missing-tools until live matrix tools are available")
    baseline_items = versions.get("Current Baseline", {}).get("openItems", [])
    if not any(item.get("captureStatus") == "tool-ready" for item in baseline_items):
        errors.append("current baseline must include a tool-ready item")
    if not any("measure_controller_resources.py" in " ".join(item.get("commands", [])) for item in baseline_items):
        errors.append("current baseline must include controller resource command")
    if not worklist.get("closureCommands"):
        errors.append("version worklist must include closure commands")

    single_summary = single_version.get("summary", {})
    single_versions = single_version.get("versions", [])
    if single_summary.get("versions") != 1 or single_summary.get("openItems") != 1:
        errors.append("single-version filter should return one open version item")
    if single_summary.get("captureReady") != 1:
        errors.append("single-version filter should preserve capture-ready count")
    if [version.get("version") for version in single_versions] != ["0.4.3"]:
        errors.append("single-version filter should return only 0.4.3")
    if single_versions and single_versions[0].get("status") != "capture-ready":
        errors.append("0.4.3 filtered worklist should be capture-ready")

    multi_summary = multi_version.get("summary", {})
    multi_names = [version.get("version") for version in multi_version.get("versions", [])]
    if multi_names != ["0.3.3", "0.4.3"]:
        errors.append(f"multi-version filter order mismatch: {multi_names!r}")
    if multi_summary.get("versions") != 2 or multi_summary.get("captureReady") != 2:
        errors.append("multi-version filter should return two capture-ready versions")

    open_summary = open_only.get("summary", {})
    open_versions = open_only.get("versions", [])
    if open_summary.get("versions") != 9 or open_summary.get("openItems") != 16:
        errors.append("open-only filter should return nine open versions and sixteen open items")
    if any(version.get("status") == "complete" for version in open_versions):
        errors.append("open-only filter must not include complete versions")

    probe_summary = probe_worklist.get("summary", {})
    probe_versions = probe_worklist.get("versions", [])
    probe_statuses = {version.get("status") for version in probe_versions if isinstance(version, dict)}
    if probe_worklist.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
        errors.append("probe worklist must report unavailable cluster access")
    if probe_summary.get("blockedByTools") != 0:
        errors.append("fake all-tools version probe should not be blocked by missing tools")
    if probe_summary.get("blockedByEnvironment") != 14:
        errors.append(
            f"expected 14 environment-blocked worklist items, got {probe_summary.get('blockedByEnvironment')!r}"
        )
    if probe_summary.get("captureReady") != 2:
        errors.append("probe worklist should leave the two non-cluster Krew items capture-ready")
    if "blocked-by-environment" not in probe_statuses:
        errors.append("probe worklist must mark affected versions blocked-by-environment")

    for path in (README, README_KO, TASKBOARD):
        text = path.read_text()
        for snippet in (WORKLIST_TOOL, VERIFY_TOOL, SCHEMA):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing version worklist detail: {snippet}")

    if errors:
        print("version-worklist: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("version-worklist: passed")
    print(f"open-items: {summary['openItems']}")
    print(f"capture-ready: {summary['captureReady']}")
    print(f"blocked-by-tools: {summary['blockedByTools']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
