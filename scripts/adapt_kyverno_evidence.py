#!/usr/bin/env python3
"""Convert Kyverno CLI JSON output into KubeActuary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RESULT_KEYS = {"pass", "fail", "warn", "error", "skip"}


def walk_results(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        result = value.get("result")
        if isinstance(result, str) and result.lower() in RESULT_KEYS:
            records.append(value)
        for child in value.values():
            records.extend(walk_results(child))
    elif isinstance(value, list):
        for item in value:
            records.extend(walk_results(item))
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in RESULT_KEYS}
    for record in records:
        result = str(record.get("result", "")).lower()
        if result in counts:
            counts[result] += 1
    return counts


def evidence(payload: dict[str, Any], source: str) -> dict[str, Any]:
    records = walk_results(payload)
    counts = summarize(records)
    failed = counts["fail"] + counts["error"]
    ok = failed == 0
    summary = (
        "kyverno: "
        f"{counts['pass']} pass, {counts['fail']} fail, {counts['warn']} warn, "
        f"{counts['error']} error, {counts['skip']} skip"
    )
    return {
        "id": "kyverno-policy",
        "ok": ok,
        "summary": summary,
        "actor": "kyverno-cli",
        "collector": "kyverno",
        "reason": "policy-pass" if ok else "policy-fail",
        "sourceRef": source,
        "policyResults": {
            "pass": counts["pass"],
            "fail": counts["fail"],
            "warn": counts["warn"],
            "error": counts["error"],
            "skip": counts["skip"],
            "total": len(records),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Kyverno JSON output into KubeActuary evidence.")
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
