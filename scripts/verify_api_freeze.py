#!/usr/bin/env python3
"""Verify the v0.9.2 public API freeze gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "schemas" / "api-freeze.v0.9.2.json"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"


def read_json(path: Path) -> Any:
    with path.open() as handle:
        return json.load(handle)


def resolve_pointer(data: Any, pointer: str) -> Any:
    if pointer == "":
        return data
    current = data
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(pointer)
    return current


def require_list_contains(actual: Any, expected: list[str], label: str, errors: list[str]) -> None:
    if not isinstance(actual, list):
        errors.append(f"{label} is not a list")
        return
    for value in expected:
        if value not in actual:
            errors.append(f"{label} missing frozen value: {value}")


def main() -> int:
    errors: list[str] = []
    contract = read_json(CONTRACT)

    if contract.get("schemaVersion") != "kube-actuary.api-freeze.v1":
        errors.append("contract schemaVersion mismatch")
    if contract.get("release") != "0.9.2":
        errors.append("contract release mismatch")
    if contract.get("policy", {}).get("mode") != "additive-only":
        errors.append("contract policy must be additive-only")

    json_schema_spec = contract.get("jsonSchema", {})
    json_schema_path = ROOT / json_schema_spec.get("path", "")
    if not json_schema_path.is_file():
        errors.append(f"json schema missing: {json_schema_path.relative_to(ROOT)}")
    else:
        json_schema = read_json(json_schema_path)
        for pointer, expected in json_schema_spec.get("equals", {}).items():
            try:
                actual = resolve_pointer(json_schema, pointer)
            except (KeyError, IndexError, ValueError):
                errors.append(f"json schema missing pointer: {pointer}")
                continue
            if actual != expected:
                errors.append(f"json schema changed at {pointer}: expected {expected!r}, got {actual!r}")
        for pointer, expected_values in json_schema_spec.get("contains", {}).items():
            try:
                actual = resolve_pointer(json_schema, pointer)
            except (KeyError, IndexError, ValueError):
                errors.append(f"json schema missing pointer: {pointer}")
                continue
            require_list_contains(actual, expected_values, f"json schema {pointer}", errors)

    crd_spec = contract.get("crd", {})
    crd_path = ROOT / crd_spec.get("path", "")
    if not crd_path.is_file():
        errors.append(f"crd missing: {crd_path.relative_to(ROOT)}")
    else:
        crd = crd_path.read_text()
        for snippet in crd_spec.get("requiredSnippets", []):
            if snippet not in crd:
                errors.append(f"crd missing frozen snippet: {snippet}")

    docs_spec = contract.get("docs", {})
    docs_path = ROOT / docs_spec.get("path", "")
    if not docs_path.is_file():
        errors.append(f"api freeze doc missing: {docs_path.relative_to(ROOT)}")
    else:
        docs = docs_path.read_text()
        for snippet in docs_spec.get("requiredSnippets", []):
            if snippet not in docs:
                errors.append(f"api freeze doc missing snippet: {snippet}")

    taskboard = TASKBOARD.read_text() if TASKBOARD.is_file() else ""
    if "API freeze and upgrade compatibility gate" not in taskboard:
        errors.append("taskboard missing v0.9.2 API freeze task")
    if "`scripts/verify_api_freeze.py`" not in taskboard:
        errors.append("taskboard missing api freeze verifier")

    if errors:
        print("api-freeze: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("api-freeze: passed")
    print(f"contract: {CONTRACT.relative_to(ROOT)}")
    print("policy: additive-only")
    print("breaking-schema-diff: guarded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
