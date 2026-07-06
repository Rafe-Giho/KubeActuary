#!/usr/bin/env python3
"""Record a local version iteration run and compare it with the previous run."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.compare_version_iterations import compare_iterations, render_markdown as render_diff_markdown  # noqa: E402
from scripts.prepare_version_iteration import prepare_iteration_pack  # noqa: E402


SCHEMA_VERSION = "kube-actuary.version-iteration-history.v1"


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "run"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_index(history_dir: Path) -> dict[str, Any]:
    path = history_dir / "index.json"
    if not path.is_file():
        return {"schemaVersion": SCHEMA_VERSION, "runs": []}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"unsupported history schema in {path}: {payload.get('schemaVersion')}")
    if not isinstance(payload.get("runs"), list):
        raise ValueError(f"history index runs must be a list: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def render_history(index: dict[str, Any]) -> str:
    lines = [
        "# KubeActuary Version Iteration History",
        "",
        f"Schema: `{index['schemaVersion']}`",
        "",
        "## Runs",
        "",
    ]
    if not index["runs"]:
        lines.append("- none")
    for run in index["runs"]:
        lines.append(
            f"- `{run['runId']}` versions={run['summary']['versions']} "
            f"open={run['summary']['openItems']} "
            f"capture-ready={run['summary']['captureReady']} "
            f"blocked-by-environment={run['summary'].get('blockedByEnvironment', 0)} "
            f"evidence-files={run['summary'].get('existingEvidenceFiles', 0)}/{run['summary'].get('evidenceFiles', 0)}"
        )
        if run.get("previousRunId"):
            lines.append(f"  previous: `{run['previousRunId']}`")
        if run.get("diffSummary"):
            diff = run["diffSummary"]
            lines.append(
                f"  diff: status-changed={diff['statusChanged']} "
                f"capture-ready-delta={diff['captureReadyDelta']} "
                f"blocked-by-environment-delta={diff['blockedByEnvironmentDelta']} "
                f"existing-evidence-files-delta={diff.get('existingEvidenceFilesDelta', 0)}"
            )
    return "\n".join(lines) + "\n"


def latest_run(index: dict[str, Any]) -> dict[str, Any] | None:
    runs = index.get("runs", [])
    return runs[-1] if runs else None


def record_iteration(
    history_dir: Path,
    run_id: str,
    created_at: str,
    version_filters: list[str],
    open_only: bool,
    probe_environment: bool,
    kubectl: str,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    history_dir.mkdir(parents=True, exist_ok=True)
    index = load_index(history_dir)
    run_id = slug(run_id)
    if any(run.get("runId") == run_id for run in index["runs"]):
        raise ValueError(f"run already exists: {run_id}")

    run_dir = history_dir / "runs" / run_id
    worklist = prepare_iteration_pack(
        run_dir,
        version_filters=version_filters,
        open_only=open_only,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
    )

    previous = latest_run(index)
    diff_summary = None
    diff_path = None
    if previous is not None:
        previous_dir = history_dir / str(previous["path"])
        diff = compare_iterations(previous_dir, run_dir)
        diff_path_obj = run_dir / "diff-from-previous.json"
        diff_markdown_path = run_dir / "diff-from-previous.md"
        write_json(diff_path_obj, diff)
        diff_markdown_path.write_text(render_diff_markdown(diff))
        diff_summary = diff["summary"]
        diff_path = diff_path_obj.relative_to(history_dir).as_posix()

    entry = {
        "runId": run_id,
        "createdAt": created_at,
        "path": run_dir.relative_to(history_dir).as_posix(),
        "filters": {
            "versions": list(version_filters),
            "openOnly": open_only,
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
            "evidenceDir": evidence_dir.as_posix() if evidence_dir else None,
        },
        "summary": worklist["summary"],
        "previousRunId": previous.get("runId") if previous else None,
        "diffPath": diff_path,
        "diffSummary": diff_summary,
    }
    index["runs"].append(entry)
    write_json(history_dir / "index.json", index)
    (history_dir / "README.md").write_text(render_history(index))
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a KubeActuary version iteration run.")
    parser.add_argument("history_dir", help="history directory to update")
    parser.add_argument("--run-id", help="stable run id; defaults to UTC timestamp")
    parser.add_argument("--created-at", help="stable creation timestamp for tests")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--open-only", action="store_true", help="include only versions with open work")
    parser.add_argument("--evidence-dir", help="optional evidence directory for resolved commands and file readiness")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    created_at = args.created_at or utc_now()
    run_id = args.run_id or created_at.replace(":", "").replace("+", "z")
    try:
        entry = record_iteration(
            Path(args.history_dir),
            run_id=run_id,
            created_at=created_at,
            version_filters=args.version,
            open_only=args.open_only,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            evidence_dir=Path(args.evidence_dir) if args.evidence_dir else None,
        )
    except ValueError as exc:
        print("version-iteration-history: failed")
        print(f"error: {exc}")
        return 1

    print(f"version-iteration-history: wrote {args.history_dir}")
    print(f"run-id: {entry['runId']}")
    print(f"versions: {entry['summary']['versions']}")
    print(f"open-items: {entry['summary']['openItems']}")
    print(f"capture-ready: {entry['summary']['captureReady']}")
    print(f"blocked-by-tools: {entry['summary']['blockedByTools']}")
    print(f"blocked-by-environment: {entry['summary'].get('blockedByEnvironment', 0)}")
    print(f"evidence-files: {entry['summary'].get('existingEvidenceFiles', 0)}/{entry['summary'].get('evidenceFiles', 0)}")
    if entry.get("previousRunId"):
        print(f"previous-run-id: {entry['previousRunId']}")
        print(f"diff-path: {entry['diffPath']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
