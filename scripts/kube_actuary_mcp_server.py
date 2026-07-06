#!/usr/bin/env python3
"""Minimal stdio JSON-RPC/MCP wrapper for safe KubeActuary tools."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "kube-actuary"
PROTOCOL_VERSION = "2024-11-05"


TOOLS: list[dict[str, Any]] = [
    {
        "name": "draft_operation_capsule",
        "description": "Create an OperationCapsule draft from intent plus a command or manifest path.",
        "inputSchema": {
            "type": "object",
            "required": ["intent"],
            "properties": {
                "intent": {"type": "string"},
                "command": {"type": "string"},
                "manifestPath": {"type": "string"},
                "actor": {"type": "string"},
                "context": {"type": "string"},
                "namespace": {"type": "string"},
            },
        },
    },
    {
        "name": "inspect_operation_capsule",
        "description": "Summarize target, risk, evidence, and state for a capsule.",
        "inputSchema": {"type": "object", "required": ["capsule"], "properties": {"capsule": {"type": "object"}}},
    },
    {
        "name": "attach_operation_evidence",
        "description": "Attach an evidence record to a capsule and return the updated capsule JSON.",
        "inputSchema": {
            "type": "object",
            "required": ["capsule", "id", "summary"],
            "properties": {
                "capsule": {"type": "object"},
                "id": {"type": "string"},
                "summary": {"type": "string"},
                "actor": {"type": "string"},
                "source": {"type": "string"},
                "fail": {"type": "boolean"},
                "allowExtra": {"type": "boolean"},
            },
        },
    },
    {
        "name": "verify_operation_capsule",
        "description": "Check required evidence for a capsule.",
        "inputSchema": {"type": "object", "required": ["capsule"], "properties": {"capsule": {"type": "object"}}},
    },
    {
        "name": "gate_operation_capsule",
        "description": "Return the open/closed execution decision for a capsule.",
        "inputSchema": {"type": "object", "required": ["capsule"], "properties": {"capsule": {"type": "object"}}},
    },
]


def required(arguments: dict[str, Any], key: str) -> Any:
    value = arguments.get(key)
    if value is None or value == "":
        raise ValueError(f"missing required argument: {key}")
    return value


def tool_result(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_capsule(path: Path, capsule: Any) -> None:
    if not isinstance(capsule, dict):
        raise ValueError("capsule must be an object")
    path.write_text(json.dumps(capsule) + "\n")


def cli_tool_result(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = result.stdout
    if result.returncode != 0 and result.stderr:
        text = f"{text}{result.stderr}"
    return tool_result(text.strip(), is_error=result.returncode != 0)


def draft_operation_capsule(arguments: dict[str, Any]) -> dict[str, Any]:
    args = ["draft", "--intent", str(required(arguments, "intent")), "--out", "-"]
    args.extend(["--actor", str(arguments.get("actor", "mcp-agent"))])
    if arguments.get("command"):
        args.extend(["--command", str(arguments["command"])])
    if arguments.get("manifestPath"):
        args.extend(["--manifest", str(arguments["manifestPath"])])
    if arguments.get("context"):
        args.extend(["--context", str(arguments["context"])])
    if arguments.get("namespace"):
        args.extend(["--namespace", str(arguments["namespace"])])
    return cli_tool_result(run_cli(args))


def inspect_operation_capsule(arguments: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "capsule.json"
        write_capsule(path, required(arguments, "capsule"))
        return cli_tool_result(run_cli(["inspect", str(path)]))


def attach_operation_evidence(arguments: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        capsule_path = Path(tmpdir) / "capsule.json"
        output_path = Path(tmpdir) / "capsule.out.json"
        write_capsule(capsule_path, required(arguments, "capsule"))
        args = [
            "attach-evidence",
            str(capsule_path),
            "--id",
            str(required(arguments, "id")),
            "--summary",
            str(required(arguments, "summary")),
            "--actor",
            str(arguments.get("actor", "mcp-agent")),
            "--out",
            str(output_path),
        ]
        if arguments.get("source"):
            args.extend(["--source", str(arguments["source"])])
        if arguments.get("fail"):
            args.append("--fail")
        if arguments.get("allowExtra"):
            args.append("--allow-extra")
        result = run_cli(args)
        if result.returncode != 0:
            return cli_tool_result(result)
        return tool_result(output_path.read_text())


def verify_operation_capsule(arguments: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "capsule.json"
        write_capsule(path, required(arguments, "capsule"))
        return cli_tool_result(run_cli(["verify", str(path)]))


def gate_operation_capsule(arguments: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "capsule.json"
        write_capsule(path, required(arguments, "capsule"))
        return cli_tool_result(run_cli(["gate", str(path)]))


HANDLERS = {
    "draft_operation_capsule": draft_operation_capsule,
    "inspect_operation_capsule": inspect_operation_capsule,
    "attach_operation_evidence": attach_operation_evidence,
    "verify_operation_capsule": verify_operation_capsule,
    "gate_operation_capsule": gate_operation_capsule,
}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    try:
        if method == "initialize":
            return success_response(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "kube-actuary", "version": "0.2.0"},
                },
            )
        if method == "tools/list":
            return success_response(request_id, {"tools": TOOLS})
        if method == "tools/call":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            name = params.get("name")
            if name not in HANDLERS:
                return error_response(request_id, -32601, f"tool not found: {name}")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            return success_response(request_id, HANDLERS[name](arguments))
        if request_id is None:
            return None
        return error_response(request_id, -32601, f"method not found: {method}")
    except Exception as exc:
        return error_response(request_id, -32603, str(exc))


def read_message(stream: Any) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("ascii").partition(":")
        headers[key.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream: Any, message: dict[str, Any]) -> None:
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


def main() -> int:
    while True:
        request = read_message(sys.stdin.buffer)
        if request is None:
            return 0
        response = handle_request(request)
        if response is not None:
            write_message(sys.stdout.buffer, response)


if __name__ == "__main__":
    raise SystemExit(main())
