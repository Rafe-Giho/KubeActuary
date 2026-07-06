#!/usr/bin/env python3
"""Convert kube-linter JSON output into KubeActuary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def report_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("Reports", "reports", "Checks", "checks", "Problems", "problems", "diagnostics"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def severity(record: dict[str, Any]) -> str:
    for key in ("severity", "Severity"):
        if isinstance(record.get(key), str):
            return record[key].lower()
    diagnostic = record.get("Diagnostic")
    if isinstance(diagnostic, dict) and isinstance(diagnostic.get("Severity"), str):
        return diagnostic["Severity"].lower()
    return "warning"


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for record in records:
        level = severity(record)
        if level in ("error", "critical"):
            counts["error"] += 1
        elif level in ("info", "notice"):
            counts["info"] += 1
        else:
            counts["warning"] += 1
    return counts


def normalized_severity(counts: dict[str, int]) -> str:
    if counts["error"]:
        return "error"
    if counts["warning"]:
        return "warning"
    if counts["info"]:
        return "info"
    return "none"


def evidence(payload: dict[str, Any], source: str) -> dict[str, Any]:
    records = report_items(payload)
    counts = summarize(records)
    ok = not records
    summary = (
        "kube-linter: "
        f"{len(records)} issue(s), {counts['error']} error, "
        f"{counts['warning']} warning, {counts['info']} info"
    )
    return {
        "id": "kube-linter-policy",
        "ok": ok,
        "summary": summary,
        "actor": "kube-linter-cli",
        "collector": "kube-linter",
        "reason": "policy-pass" if ok else "policy-fail",
        "severity": normalized_severity(counts),
        "sourceRef": source,
        "policyResults": {
            "issues": len(records),
            "error": counts["error"],
            "warning": counts["warning"],
            "info": counts["info"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert kube-linter JSON output into KubeActuary evidence.")
    parser.add_argument("input")
    parser.add_argument("--out", default="-")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text())
    result = evidence(payload, args.input)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        Path(args.out).write_text(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
