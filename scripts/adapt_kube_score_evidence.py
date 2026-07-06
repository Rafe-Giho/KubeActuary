#!/usr/bin/env python3
"""Convert kube-score JSON output into KubeActuary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def normalize_grade(value: Any) -> str:
    if isinstance(value, int):
        if value <= 1:
            return "critical"
        if value <= 5:
            return "warning"
        return "ok"
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("critical", "error", "fail", "failed"):
            return "critical"
        if text in ("warning", "warn"):
            return "warning"
        if text in ("ok", "almostok", "almost_ok", "allok", "all_ok", "pass", "passed"):
            return "ok"
        if text in ("skip", "skipped"):
            return "skipped"
    return "unknown"


def looks_like_check(record: dict[str, Any]) -> bool:
    return any(key in record for key in ("Grade", "grade", "Skipped", "skipped", "Check", "check", "checkID", "check_id"))


def collect_checks(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        for key in ("Checks", "checks", "checksResults", "checkResults", "results"):
            checks = value.get(key)
            if isinstance(checks, list) and all(isinstance(item, dict) for item in checks):
                direct = [item for item in checks if looks_like_check(item)]
                if direct:
                    return direct

                records: list[dict[str, Any]] = []
                for item in checks:
                    records.extend(collect_checks(item))
                return records
        if looks_like_check(value):
            return [value]

        records = []
        for child in value.values():
            records.extend(collect_checks(child))
        return records

    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for child in value:
            records.extend(collect_checks(child))
        return records

    return []


def check_grade(record: dict[str, Any]) -> str:
    if record.get("Skipped") is True or record.get("skipped") is True:
        return "skipped"
    for key in ("Grade", "grade", "score", "severity"):
        if key in record:
            return normalize_grade(record[key])
    return "unknown"


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "ok": 0, "skipped": 0, "unknown": 0}
    for record in records:
        grade = check_grade(record)
        counts[grade if grade in counts else "unknown"] += 1
    return counts


def normalized_severity(counts: dict[str, int]) -> str:
    if counts["critical"]:
        return "critical"
    if counts["warning"] or counts["unknown"]:
        return "warning"
    return "none"


def evidence(payload: Any, source: str) -> dict[str, Any]:
    records = collect_checks(payload)
    counts = summarize(records)
    failing = counts["critical"] + counts["warning"] + counts["unknown"]
    ok = failing == 0
    summary = (
        "kube-score: "
        f"{len(records)} check(s), {counts['critical']} critical, "
        f"{counts['warning']} warning, {counts['ok']} ok, "
        f"{counts['skipped']} skipped"
    )
    return {
        "id": "kube-score-policy",
        "ok": ok,
        "summary": summary,
        "actor": "kube-score-cli",
        "collector": "kube-score",
        "reason": "policy-pass" if ok else "policy-fail",
        "severity": normalized_severity(counts),
        "sourceRef": source,
        "policyResults": {
            "checks": len(records),
            "critical": counts["critical"],
            "warning": counts["warning"],
            "ok": counts["ok"],
            "skipped": counts["skipped"],
            "unknown": counts["unknown"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert kube-score JSON output into KubeActuary evidence.")
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
