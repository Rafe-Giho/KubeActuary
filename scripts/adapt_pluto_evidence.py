#!/usr/bin/env python3
"""Convert Pluto JSON output into KubeActuary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("items")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def replacement_api(item: dict[str, Any]) -> str:
    api = item.get("api")
    if isinstance(api, dict):
        value = api.get("replacement-api") or api.get("replacementApi")
        if isinstance(value, str):
            return value.strip()
    return ""


def finding_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"deprecated": 0, "removed": 0, "unavailableReplacement": 0, "unknown": 0}
    for record in records:
        deprecated = record.get("deprecated")
        removed = record.get("removed")
        if removed is True:
            counts["removed"] += 1
        elif deprecated is True:
            counts["deprecated"] += 1
        else:
            counts["unknown"] += 1

        if (deprecated is True or removed is True) and not replacement_api(record):
            counts["unavailableReplacement"] += 1
    return counts


def target_versions(payload: dict[str, Any]) -> dict[str, str]:
    value = payload.get("target-versions") or payload.get("targetVersions")
    if not isinstance(value, dict):
        return {}
    return {str(key): str(version) for key, version in sorted(value.items())}


def normalized_severity(counts: dict[str, int]) -> str:
    if counts["removed"]:
        return "critical"
    if counts["deprecated"] or counts["unavailableReplacement"] or counts["unknown"]:
        return "warning"
    return "none"


def evidence(payload: dict[str, Any], source: str) -> dict[str, Any]:
    records = items(payload)
    counts = finding_counts(records)
    ok = len(records) == 0
    summary = (
        "pluto: "
        f"{len(records)} deprecated API finding(s), {counts['removed']} removed, "
        f"{counts['deprecated']} deprecated, "
        f"{counts['unavailableReplacement']} unavailable replacement"
    )
    return {
        "id": "pluto-deprecated-api",
        "ok": ok,
        "summary": summary,
        "actor": "pluto-cli",
        "collector": "pluto",
        "reason": "api-compatible" if ok else "deprecated-api-found",
        "severity": normalized_severity(counts),
        "sourceRef": source,
        "deprecatedApiResults": {
            "items": len(records),
            "deprecated": counts["deprecated"],
            "removed": counts["removed"],
            "unavailableReplacement": counts["unavailableReplacement"],
            "unknown": counts["unknown"],
            "targetVersions": target_versions(payload),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Pluto JSON output into KubeActuary evidence.")
    parser.add_argument("input")
    parser.add_argument("--out", default="-")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text())
    if not isinstance(payload, dict):
        raise SystemExit("pluto JSON root must be an object")

    result = evidence(payload, args.input)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        Path(args.out).write_text(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
