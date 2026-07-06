#!/usr/bin/env python3
"""Convert OPA eval JSON output into KubeActuary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def expression_values(payload: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for result in payload.get("result", []):
        if not isinstance(result, dict):
            continue
        for expression in result.get("expressions", []):
            if isinstance(expression, dict) and "value" in expression:
                values.append(expression["value"])
    return values


def violation_items(value: Any) -> list[Any]:
    if value is False:
        return [False]
    if value in (True, None):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if "deny" in value:
            return violation_items(value["deny"])
        if "violations" in value:
            return violation_items(value["violations"])
        return [value] if value else []
    if isinstance(value, str):
        return [value] if value else []
    return []


def evidence(payload: dict[str, Any], source: str) -> dict[str, Any]:
    values = expression_values(payload)
    violations: list[Any] = []
    for value in values:
        violations.extend(violation_items(value))
    ok = len(violations) == 0
    return {
        "id": "opa-rego-policy",
        "ok": ok,
        "summary": f"opa: {len(violations)} violation(s) across {len(values)} expression(s)",
        "actor": "opa-cli",
        "collector": "opa",
        "reason": "policy-pass" if ok else "policy-fail",
        "sourceRef": source,
        "policyResults": {
            "expressions": len(values),
            "violations": len(violations),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert OPA eval JSON output into KubeActuary evidence.")
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
