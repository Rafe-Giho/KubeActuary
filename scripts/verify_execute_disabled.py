#!/usr/bin/env python3
"""Verify execution remains disabled by default."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "kube-actuary"
MCP_SERVER = ROOT / "scripts" / "kube_actuary_mcp_server.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_mcp_server() -> Any:
    spec = importlib.util.spec_from_file_location("kube_actuary_mcp_server", MCP_SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load MCP server module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mcp_call(server: Any, name: str) -> dict[str, Any]:
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {}}}
    )
    if not isinstance(response, dict):
        raise AssertionError("MCP call returned no response")
    return response


def main() -> int:
    errors: list[str] = []

    commands = run_cli("help", "commands")
    if commands.returncode != 0:
        errors.append(f"help commands failed: {commands.stderr.strip()}")
    if "execute" in commands.stdout:
        errors.append("CLI command help must not list execute")

    execute = run_cli("execute", "--help")
    if execute.returncode == 0:
        errors.append("CLI execute command unexpectedly exists")

    agent_help = run_cli("help", "agents", "--format", "json")
    if agent_help.returncode != 0:
        errors.append(f"agent help failed: {agent_help.stderr.strip()}")
        payload: dict[str, Any] = {}
    else:
        payload = json.loads(agent_help.stdout)

    command_names = {command.get("name") for command in payload.get("commands", []) if isinstance(command, dict)}
    if any(name and "execute" in name for name in command_names):
        errors.append("agent command contract must not expose execute")
    never_executes = payload.get("agentContract", {}).get("neverExecutes", [])
    if "the capsule spec.proposedCommand" not in never_executes:
        errors.append("agent contract must state proposedCommand is never executed")

    server = load_mcp_server()
    tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool.get("name") for tool in tools.get("result", {}).get("tools", []) if isinstance(tool, dict)}
    if any(name and "execute" in name for name in names):
        errors.append("MCP tools/list must not expose execute")
    execute_response = mcp_call(server, "execute_approved_capsule")
    if execute_response.get("error", {}).get("code") != -32601:
        errors.append("MCP execute_approved_capsule must be disabled")

    if errors:
        print("execute-disabled: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("execute-disabled: passed")
    print("cli-execute: absent")
    print("mcp-execute: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
