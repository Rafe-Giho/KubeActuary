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


def readme_text(evidence_dir: Path, queue: dict) -> str:
    summary = queue["summary"]
    return "\n".join(
        [
            "# KubeActuary Live Evidence Directory",
            "",
            "This directory is prepared for external validation evidence capture.",
            "",
            f"- schema: `{queue['schemaVersion']}`",
            f"- evidence-dir: `{evidence_dir.as_posix()}`",
            "- cluster-writes: `disabled`",
            f"- queue-items: {summary['total']}",
            f"- tool-ready: {summary['toolReady']}/{summary['total']}",
            "",
            "Use the generated queue files in `.kubeactuary/` to capture reports,",
            "raw command output, and supplemental evidence into the prepared",
            "`reports/`, `raw/`, and `supplemental/` directories.",
            "Use `.kubeactuary/next-version-task.*` for the deterministic next",
            "task and its resolved evidence paths.",
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


def prepare_directory(evidence_dir: Path) -> dict[str, Path | dict]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (evidence_dir / subdir).mkdir(parents=True, exist_ok=True)

    queue = build_queue(evidence_dir)
    metadata_dir = evidence_dir / ".kubeactuary"
    queue_json = metadata_dir / QUEUE_JSON
    queue_md = metadata_dir / QUEUE_MD
    next_task = build_selection(
        version_filters=[],
        include_complete=False,
        probe_environment=False,
        kubectl="kubectl",
        evidence_dir=evidence_dir,
    )
    next_task_json = metadata_dir / NEXT_TASK_JSON
    next_task_md = metadata_dir / NEXT_TASK_MD
    readme = evidence_dir / "README.md"
    write_text(queue_json, json.dumps(queue, indent=2, sort_keys=True))
    write_text(queue_md, render_markdown(queue))
    write_text(next_task_json, json.dumps(next_task, indent=2, sort_keys=True))
    write_text(next_task_md, render_next_task_markdown(next_task))
    write_text(readme, readme_text(evidence_dir, queue))
    return {
        "queue": queue,
        "queueJson": queue_json,
        "queueMarkdown": queue_md,
        "nextTask": next_task,
        "nextTaskJson": next_task_json,
        "nextTaskMarkdown": next_task_md,
        "readme": readme,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a KubeActuary live evidence directory.")
    parser.add_argument("evidence_dir", help="directory to create or update")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    try:
        result = prepare_directory(evidence_dir)
    except OSError as exc:
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
    print(f"queue: {result['queueJson']}")
    print(f"next-task: {result['nextTaskJson']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
