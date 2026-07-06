#!/usr/bin/env python3
"""Prepare a local directory for live validation evidence capture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_live_validation_queue import build_queue, render_markdown  # noqa: E402
from scripts.select_next_version_task import build_selection, render_markdown as render_next_task_markdown  # noqa: E402


SUBDIRS = ("reports", "raw", "supplemental", ".kubeactuary")
QUEUE_JSON = "live-validation-queue.json"
QUEUE_MD = "live-validation-queue.md"
NEXT_TASK_JSON = "next-version-task.json"
NEXT_TASK_MD = "next-version-task.md"
ENVIRONMENT_PROBE_JSON = "environment-probe.json"
ENVIRONMENT_PROBE_MD = "environment-probe.md"
ENVIRONMENT_PROBE_SCHEMA = "kube-actuary.environment-probe.v1"
ENVIRONMENT_BLOCKERS_JSON = "environment-blockers.json"
ENVIRONMENT_BLOCKERS_MD = "environment-blockers.md"
ENVIRONMENT_BLOCKERS_SCHEMA = "kube-actuary.environment-blockers.v1"


def readme_text(evidence_dir: Path, queue: dict) -> str:
    summary = queue["summary"]
    environment_probe = queue.get("environmentProbe") or {}
    probe_line = (
        f"- environment-probe: `{environment_probe.get('clusterAccess')}`"
        if environment_probe
        else "- environment-probe: `not-run`"
    )
    return "\n".join(
        [
            "# KubeActuary Live Evidence Directory",
            "",
            "This directory is prepared for external validation evidence capture.",
            "",
            f"- schema: `{queue['schemaVersion']}`",
            f"- evidence-dir: `{evidence_dir.as_posix()}`",
            "- cluster-writes: `disabled`",
            probe_line,
            f"- queue-items: {summary['total']}",
            f"- tool-ready: {summary['toolReady']}/{summary['total']}",
            "",
            "Use the generated queue files in `.kubeactuary/` to capture reports,",
            "raw command output, and supplemental evidence into the prepared",
            "`reports/`, `raw/`, and `supplemental/` directories.",
            "Use `.kubeactuary/next-version-task.*` for the deterministic next",
            "task and its resolved evidence paths.",
            "After a selected task's evidence files exist, rerun this helper with",
            "`--skip-complete-evidence` to advance the next-task artifact.",
            "",
            "Closure commands:",
            "",
            f"- `python3 -B scripts/verify_live_validation_queue_safety.py`",
            f"- `python3 -B scripts/build_release_evidence_directory.py {evidence_dir.as_posix()}`",
            "",
        ]
    )


def write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n")


def environment_probe_report(evidence_dir: Path, queue: dict) -> dict:
    environment_probe = queue.get("environmentProbe") if isinstance(queue.get("environmentProbe"), dict) else {}
    checks = environment_probe.get("checks", [])
    return {
        "schemaVersion": ENVIRONMENT_PROBE_SCHEMA,
        "evidenceDir": evidence_dir.as_posix(),
        "clusterWrites": "disabled",
        "probeEnabled": bool(environment_probe),
        "kubectl": environment_probe.get("kubectl"),
        "clusterAccess": environment_probe.get("clusterAccess", "not-run"),
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for check in checks if isinstance(check, dict) and check.get("ok") is True),
            "failed": sum(1 for check in checks if isinstance(check, dict) and check.get("ok") is not True),
        },
    }


def render_environment_probe(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# KubeActuary Environment Probe",
        "",
        f"Schema: `{report['schemaVersion']}`",
        f"Evidence directory: `{report['evidenceDir']}`",
        f"Cluster writes: `{report['clusterWrites']}`",
        f"Probe enabled: {str(report['probeEnabled']).lower()}",
        f"Cluster access: `{report['clusterAccess']}`",
        "",
        "## Summary",
        "",
        f"- checks: {summary['checks']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        "",
        "## Checks",
        "",
    ]
    if report.get("checks"):
        for check in report["checks"]:
            status = "passed" if check.get("ok") else "failed"
            command = " ".join(str(part) for part in check.get("command", []))
            lines.append(f"- `{status}` {check.get('name')}: `{command}`")
            if check.get("exitCode") is not None:
                lines.append(f"  exit code: {check.get('exitCode')}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def environment_blocker_report(evidence_dir: Path, queue: dict, next_task: dict) -> dict:
    environment_probe = queue.get("environmentProbe") or {}
    blocked_items = [
        {
            "id": item.get("id"),
            "version": item.get("version"),
            "item": item.get("item"),
            "kind": item.get("kind"),
            "status": item.get("status"),
            "environmentStatus": item.get("environmentStatus"),
            "nextStep": item.get("nextStep"),
        }
        for item in queue.get("items", [])
        if isinstance(item, dict) and item.get("status") == "blocked-by-environment"
    ]
    selected = next_task.get("selected") or {}
    return {
        "schemaVersion": ENVIRONMENT_BLOCKERS_SCHEMA,
        "evidenceDir": evidence_dir.as_posix(),
        "clusterWrites": "disabled",
        "environmentProbe": environment_probe or None,
        "summary": {
            "clusterAccess": environment_probe.get("clusterAccess", "not-run"),
            "blockedByEnvironment": len(blocked_items),
            "selectedBlocked": selected.get("captureStatus") == "blocked-by-environment",
        },
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
            "environmentStatus": selected.get("environmentStatus"),
            "nextStep": selected.get("nextStep"),
        },
        "items": blocked_items,
    }


def render_environment_blockers(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# KubeActuary Environment Blockers",
        "",
        f"Schema: `{report['schemaVersion']}`",
        f"Evidence directory: `{report['evidenceDir']}`",
        f"Cluster writes: `{report['clusterWrites']}`",
        "",
        "## Summary",
        "",
        f"- cluster access: `{summary['clusterAccess']}`",
        f"- blocked by environment: {summary['blockedByEnvironment']}",
        f"- selected blocked: {str(summary['selectedBlocked']).lower()}",
        "",
        "## Selected",
        "",
    ]
    selected = report.get("selected") or {}
    if selected.get("id"):
        lines.append(f"- `{selected.get('id')}` {selected.get('item')} ({selected.get('captureStatus')})")
        if selected.get("environmentStatus"):
            lines.append(f"  environment: `{selected.get('environmentStatus')}`")
        if selected.get("nextStep"):
            lines.append(f"  next: {selected.get('nextStep')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Blocked Items", ""])
    if report.get("items"):
        for item in report["items"]:
            lines.append(f"- `{item.get('id')}` {item.get('item')} ({item.get('version')})")
            if item.get("environmentStatus"):
                lines.append(f"  environment: `{item.get('environmentStatus')}`")
            if item.get("nextStep"):
                lines.append(f"  next: {item.get('nextStep')}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def prepare_directory(
    evidence_dir: Path,
    skip_complete_evidence: bool = False,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
) -> dict[str, Path | dict]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (evidence_dir / subdir).mkdir(parents=True, exist_ok=True)

    queue = build_queue(evidence_dir, probe_environment=probe_environment, kubectl=kubectl)
    metadata_dir = evidence_dir / ".kubeactuary"
    queue_json = metadata_dir / QUEUE_JSON
    queue_md = metadata_dir / QUEUE_MD
    probe_json = metadata_dir / ENVIRONMENT_PROBE_JSON
    probe_md = metadata_dir / ENVIRONMENT_PROBE_MD
    blockers_json = metadata_dir / ENVIRONMENT_BLOCKERS_JSON
    blockers_md = metadata_dir / ENVIRONMENT_BLOCKERS_MD
    write_text(queue_json, json.dumps(queue, indent=2, sort_keys=True))
    next_task = build_selection(
        version_filters=[],
        include_complete=False,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        skip_complete_evidence=skip_complete_evidence,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
    )
    next_task_json = metadata_dir / NEXT_TASK_JSON
    next_task_md = metadata_dir / NEXT_TASK_MD
    readme = evidence_dir / "README.md"
    probe = environment_probe_report(evidence_dir, queue)
    blockers = environment_blocker_report(evidence_dir, queue, next_task)
    write_text(queue_md, render_markdown(queue))
    write_text(probe_json, json.dumps(probe, indent=2, sort_keys=True))
    write_text(probe_md, render_environment_probe(probe))
    write_text(next_task_json, json.dumps(next_task, indent=2, sort_keys=True))
    write_text(next_task_md, render_next_task_markdown(next_task))
    write_text(blockers_json, json.dumps(blockers, indent=2, sort_keys=True))
    write_text(blockers_md, render_environment_blockers(blockers))
    write_text(readme, readme_text(evidence_dir, queue))
    return {
        "queue": queue,
        "queueJson": queue_json,
        "queueMarkdown": queue_md,
        "environmentProbe": probe,
        "environmentProbeJson": probe_json,
        "environmentProbeMarkdown": probe_md,
        "environmentBlockers": blockers,
        "environmentBlockersJson": blockers_json,
        "environmentBlockersMarkdown": blockers_md,
        "nextTask": next_task,
        "nextTaskJson": next_task_json,
        "nextTaskMarkdown": next_task_md,
        "readme": readme,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a KubeActuary live evidence directory.")
    parser.add_argument("evidence_dir", help="directory to create or update")
    parser.add_argument(
        "--skip-complete-evidence",
        action="store_true",
        help="advance next-task artifacts past tasks whose resolved evidence files already exist",
    )
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    parser.add_argument("--capture-status", action="append", default=[], help="filter next-task selection by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter next-task selection by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter next-task selection by environment status; repeatable")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    try:
        result = prepare_directory(
            evidence_dir,
            skip_complete_evidence=args.skip_complete_evidence,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            capture_status_filters=args.capture_status,
            missing_tool_filters=args.missing_tool,
            environment_status_filters=args.environment_status,
        )
    except (OSError, ValueError) as exc:
        print("live-evidence-directory: failed")
        print(f"error: {exc}")
        return 1

    queue = result["queue"]
    summary = queue["summary"]
    print("live-evidence-directory: prepared")
    print(f"directory: {evidence_dir}")
    print(f"queue-items: {summary['total']}")
    print(f"tool-ready: {summary['toolReady']}/{summary['total']}")
    print("cluster-writes: disabled")
    print(f"probe-environment: {str(args.probe_environment).lower()}")
    if queue.get("environmentProbe"):
        print(f"cluster-access: {queue['environmentProbe'].get('clusterAccess')}")
    print(f"queue: {result['queueJson']}")
    print(f"environment-probe: {result['environmentProbeJson']}")
    print(f"environment-blockers: {result['environmentBlockersJson']}")
    print(f"next-task: {result['nextTaskJson']}")
    next_task = result["nextTask"]
    next_task_summary = next_task.get("summary", {}) if isinstance(next_task, dict) else {}
    print(f"skip-complete-evidence: {str(args.skip_complete_evidence).lower()}")
    print(f"skipped-complete-evidence: {next_task_summary.get('skippedCompleteEvidence', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
