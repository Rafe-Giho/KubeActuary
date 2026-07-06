#!/usr/bin/env python3
"""Build supplemental external evidence records from captured local files."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MEASURE = ROOT / "scripts" / "measure_controller_resources.py"
SCHEMA_VERSION = "kube-actuary.external-evidence.v1"
KINDS = ("kubectl-explain", "controller-resource-budget", "controller-live-loop")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def explain_check(text: str) -> tuple[bool, str, list[str]]:
    if not text.strip():
        return False, "kubectl explain output is empty", ["nonempty-output"]
    return True, "kubectl explain output captured", ["nonempty-output"]


def resource_budget_check(path: Path) -> tuple[bool, str, list[str]]:
    result = subprocess.run(
        [sys.executable, "-B", str(MEASURE), "--sample", str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ok = result.returncode == 0
    summary = "controller resource budget sample passed" if ok else "controller resource budget sample failed"
    return ok, summary, [line for line in result.stdout.splitlines() if line.strip()]


def controller_loop_check(text: str) -> tuple[bool, str, list[str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"controller loop output is not JSON: {exc}", ["json-parse"]
    checks = [
        "mode=server-dry-run-loop",
        "writeExecution=disabled",
        "readExecution=kubectl-get",
        "failed=0",
    ]
    ok = (
        isinstance(payload, dict)
        and payload.get("mode") == "server-dry-run-loop"
        and payload.get("writeExecution") == "disabled"
        and payload.get("readExecution") == "kubectl-get"
        and payload.get("failed") == 0
    )
    return ok, "controller loop dry-run output passed" if ok else "controller loop dry-run output failed", checks


def evaluate_source(kind: str, path: Path) -> tuple[bool, str, list[str]]:
    text = path.read_text()
    if kind == "kubectl-explain":
        return explain_check(text)
    if kind == "controller-resource-budget":
        return resource_budget_check(path)
    if kind == "controller-live-loop":
        return controller_loop_check(text)
    raise ValueError(f"unsupported evidence kind: {kind}")


def build_record(kind: str, source: Path, summary: str | None = None) -> dict[str, Any]:
    ok, detected_summary, checks = evaluate_source(kind, source)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": kind,
        "ok": ok,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "summary": summary or detected_summary,
        "source": {
            "path": str(source),
            "sha256": sha256(source),
            "bytes": source.stat().st_size,
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build KubeActuary supplemental external evidence.")
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--source", required=True, help="captured raw output or sample file")
    parser.add_argument("--summary")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        record = build_record(args.kind, Path(args.source), summary=args.summary)
    except (OSError, ValueError) as exc:
        print("external-evidence: failed")
        print(f"error: {exc}")
        return 1

    encoded = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(encoded, end="")
    else:
        Path(args.output).write_text(encoded)
        print(f"external-evidence: wrote {args.output}")
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
