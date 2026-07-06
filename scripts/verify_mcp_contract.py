#!/usr/bin/env python3
"""Verify safe MCP/JSON-RPC tool contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "kube_actuary_mcp_server.py"
SAFE_TOOLS = {
    "draft_operation_capsule",
    "inspect_operation_capsule",
    "attach_operation_evidence",
    "verify_operation_capsule",
    "gate_operation_capsule",
}


def load_server() -> Any:
    spec = importlib.util.spec_from_file_location("kube_actuary_mcp_server", SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load MCP server module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(server: Any, method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    response = server.handle_request(request)
    if not isinstance(response, dict):
        raise AssertionError(f"{method} returned no response")
    return response


def tool_text(response: dict[str, Any]) -> str:
    result = response.get("result")
    if not isinstance(result, dict):
        raise AssertionError(f"missing result: {response}")
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise AssertionError(f"missing tool content: {response}")
    item = content[0]
    if not isinstance(item, dict) or not isinstance(item.get("text"), str):
        raise AssertionError(f"missing text content: {response}")
    return item["text"]


def call_tool(server: Any, name: str, arguments: dict[str, Any], request_id: int) -> dict[str, Any]:
    return call(server, "tools/call", {"name": name, "arguments": arguments}, request_id=request_id)


def attach(server: Any, capsule: dict[str, Any], evidence_id: str) -> dict[str, Any]:
    response = call_tool(
        server,
        "attach_operation_evidence",
        {"capsule": capsule, "id": evidence_id, "summary": f"{evidence_id} attached", "actor": "mcp-test"},
        request_id=100,
    )
    return json.loads(tool_text(response))


def main() -> int:
    server = load_server()
    errors: list[str] = []

    initialized = call(server, "initialize", request_id=1)
    if initialized.get("result", {}).get("capabilities", {}).get("tools") != {}:
        errors.append("initialize does not advertise tools capability")

    listed = call(server, "tools/list", request_id=2)
    tools = listed.get("result", {}).get("tools", [])
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    if names != SAFE_TOOLS:
        errors.append(f"safe tool set mismatch: {sorted(names)}")
    if "execute_approved_capsule" in names:
        errors.append("execute tool must not be listed")

    draft = call_tool(
        server,
        "draft_operation_capsule",
        {"intent": "mcp contract smoke", "command": "kubectl get pods -n default", "actor": "mcp-test"},
        request_id=3,
    )
    capsule = json.loads(tool_text(draft))
    if capsule.get("kind") != "OperationCapsule":
        errors.append("draft tool did not return an OperationCapsule")

    inspect = call_tool(server, "inspect_operation_capsule", {"capsule": capsule}, request_id=4)
    if "state: drafted" not in tool_text(inspect):
        errors.append("inspect tool did not summarize drafted state")

    for evidence_id in ("intent", "parsed-target", "read-auth"):
        capsule = attach(server, capsule, evidence_id)

    verify = call_tool(server, "verify_operation_capsule", {"capsule": capsule}, request_id=5)
    if "verification: passed" not in tool_text(verify):
        errors.append("verify tool did not pass after required evidence")

    gate = call_tool(server, "gate_operation_capsule", {"capsule": capsule}, request_id=6)
    if "gate: open" not in tool_text(gate):
        errors.append("gate tool did not open after required evidence")

    execute = call_tool(server, "execute_approved_capsule", {"capsule": capsule}, request_id=7)
    if execute.get("error", {}).get("code") != -32601:
        errors.append("execute tool must be disabled")

    if errors:
        print("mcp-contract: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("mcp-contract: passed")
    print("safe-tools: 5")
    print("execute-tool: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
