#!/usr/bin/env python3
"""Verify MCP docs and client config stay safe and usable."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "mcp.md"
CONFIG = ROOT / "examples" / "mcp-client-config.json"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"

SAFE_TOOLS = (
    "draft_operation_capsule",
    "inspect_operation_capsule",
    "attach_operation_evidence",
    "verify_operation_capsule",
    "gate_operation_capsule",
)
FORBIDDEN = (
    "kubectl apply",
    "kubectl delete",
    "kubectl scale",
    "kubectl rollout restart",
)


def main() -> int:
    errors: list[str] = []
    doc = DOC.read_text() if DOC.is_file() else ""
    config = json.loads(CONFIG.read_text()) if CONFIG.is_file() else {}

    server = config.get("mcpServers", {}).get("kube-actuary", {})
    if server.get("command") != "python3":
        errors.append("MCP config command must be python3")
    if server.get("args") != ["-B", "scripts/kube_actuary_mcp_server.py"]:
        errors.append("MCP config args must point to the stdlib server")
    if server.get("env") != {}:
        errors.append("MCP config env must be empty by default")

    for tool in SAFE_TOOLS:
        if tool not in doc:
            errors.append(f"MCP docs missing safe tool: {tool}")
    for snippet in (
        "examples/mcp-client-config.json",
        "execute_approved_capsule` remains disabled",
        "python3 -B scripts/verify_mcp_contract.py",
        "python3 -B scripts/verify_mcp_docs.py",
    ):
        if snippet not in doc:
            errors.append(f"MCP docs missing: {snippet}")

    for forbidden in FORBIDDEN:
        if forbidden in doc and forbidden not in ("kubectl apply", "kubectl delete"):
            errors.append(f"MCP docs include forbidden write command: {forbidden}")
    if "The wrapper never runs\n`kubectl apply`, `kubectl delete`" not in doc:
        errors.append("MCP docs must state kubectl apply/delete are never run")

    taskboard = TASKBOARD.read_text() if TASKBOARD.is_file() else ""
    if "MCP server | DONE" not in taskboard:
        errors.append("taskboard must mark MCP server DONE")

    if errors:
        print("mcp-docs: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("mcp-docs: passed")
    print("client-config: examples/mcp-client-config.json")
    print("safe-tools: 5")
    print("execute-tool: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
