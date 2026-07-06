#!/usr/bin/env python3
"""Capture controller kubectl top output for resource-budget evidence."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.measure_controller_resources import (  # noqa: E402
    DEFAULT_NAMESPACE,
    DEFAULT_SELECTOR,
    build_payload,
)


SCHEMA_VERSION = "kube-actuary.controller-resource-capture.v1"


def kubectl_top_command(kubectl: str, namespace: str, selector: str) -> list[str]:
    return [*shlex.split(kubectl), "top", "pod", "-n", namespace, "-l", selector, "--containers"]


def plan(args: argparse.Namespace) -> dict[str, Any]:
    command = kubectl_top_command(args.kubectl, args.namespace, args.selector)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "run" if args.run else "plan",
        "clusterWrites": "disabled",
        "command": command,
        "output": args.output,
        "namespace": args.namespace,
        "selector": args.selector,
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"controller-resource-capture: {payload['mode']}",
        f"cluster-writes: {payload['clusterWrites']}",
        f"command: {shlex.join(payload['command'])}",
        f"output: {payload['output']}",
    ]
    if "measurement" in payload:
        measurement = payload["measurement"]
        observed = measurement.get("observed", {})
        budget = measurement.get("budget", {})
        lines.extend(
            [
                f"resource-measurement: {'passed' if measurement.get('ok') else 'failed'}",
                f"cpu-millicores: {observed.get('cpuMillicores')}",
                f"memory-mi: {observed.get('memoryMi')}",
                f"sample-count: {measurement.get('sampleCount')}",
                f"budget-cpu-millicores-less-than: {budget.get('cpuMillicoresLessThan')}",
                f"budget-memory-mi-less-than: {budget.get('memoryMiLessThan')}",
            ]
        )
    if payload.get("error"):
        lines.append(f"error: {payload['error']}")
    return "\n".join(lines) + "\n"


def write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run_capture(args: argparse.Namespace) -> dict[str, Any]:
    payload = plan(args)
    command = payload["command"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload["capturedAt"] = datetime.now(timezone.utc).isoformat()
    payload["exitCode"] = result.returncode
    payload["stderr"] = result.stderr
    if result.returncode != 0:
        payload["mode"] = "failed"
        payload["error"] = result.stderr.strip() or result.stdout.strip() or "kubectl top failed"
        return payload

    output = Path(args.output)
    write_output(output, result.stdout)
    measure_args = argparse.Namespace(sample=str(output), namespace=args.namespace, selector=args.selector)
    try:
        payload["measurement"] = build_payload(measure_args, result.stdout)
    except ValueError as exc:
        payload["mode"] = "failed"
        payload["error"] = str(exc)
        return payload
    payload["mode"] = "captured" if payload["measurement"].get("ok") is True else "failed"
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture kubectl top output for controller resource evidence.")
    parser.add_argument("--output", required=True, help="raw kubectl top output path")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--selector", default=DEFAULT_SELECTOR)
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--run", action="store_true", help="execute kubectl top instead of printing the plan")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        payload = run_capture(args) if args.run else plan(args)
    except (OSError, ValueError) as exc:
        payload = {
            **plan(args),
            "mode": "failed",
            "error": str(exc),
        }

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_text(payload)
    print(rendered, end="")
    return 0 if payload["mode"] in {"plan", "captured"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
