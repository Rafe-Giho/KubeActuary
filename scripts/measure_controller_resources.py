#!/usr/bin/env python3
"""Measure or evaluate controller resource usage against the v0.4.3 budget."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


CPU_BUDGET_MILLICORES = 50
MEMORY_BUDGET_MI = 64
DEFAULT_NAMESPACE = "kubeactuary-system"
DEFAULT_SELECTOR = "app.kubernetes.io/name=kubeactuary,app.kubernetes.io/component=controller"
SCHEMA_VERSION = "kube-actuary.controller-resource-measurement.v1"


def parse_cpu_millicores(value: str) -> int:
    value = value.strip()
    if value.endswith("m"):
        return int(value[:-1])
    return int(float(value) * 1000)


def parse_memory_mi(value: str) -> int:
    value = value.strip()
    units = (
        ("Ki", 1 / 1024),
        ("Mi", 1),
        ("Gi", 1024),
        ("Ti", 1024 * 1024),
    )
    for suffix, multiplier in units:
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * multiplier)
    return int(int(value) / 1024 / 1024)


def parse_top_samples(output: str) -> list[tuple[int, int]]:
    samples: list[tuple[int, int]] = []
    for line in output.splitlines():
        if not line.strip() or line.lower().startswith("pod "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        cpu = parse_cpu_millicores(parts[-2])
        memory = parse_memory_mi(parts[-1])
        samples.append((cpu, memory))
    if not samples:
        raise ValueError("no controller resource samples found")
    return samples


def parse_top_output(output: str) -> tuple[int, int]:
    samples = parse_top_samples(output)
    return max(cpu for cpu, _memory in samples), max(memory for _cpu, memory in samples)


def measurement_command(namespace: str, selector: str) -> list[str]:
    return ["kubectl", "top", "pod", "-n", namespace, "-l", selector, "--containers"]


def read_sample(args: argparse.Namespace) -> str:
    if args.sample:
        return Path(args.sample).read_text()
    result = subprocess.run(
        measurement_command(args.namespace, args.selector),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "kubectl top failed")
    return result.stdout


def build_payload(args: argparse.Namespace, output: str) -> dict[str, Any]:
    samples = parse_top_samples(output)
    cpu_m = max(cpu for cpu, _memory in samples)
    memory_mi = max(memory for _cpu, memory in samples)
    ok = cpu_m < CPU_BUDGET_MILLICORES and memory_mi < MEMORY_BUDGET_MI
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "ok": ok,
        "source": "sample" if args.sample else "kubectl",
        "samplePath": args.sample,
        "namespace": args.namespace,
        "selector": args.selector,
        "command": measurement_command(args.namespace, args.selector),
        "sampleCount": len(samples),
        "observed": {
            "cpuMillicores": cpu_m,
            "memoryMi": memory_mi,
        },
        "budget": {
            "cpuMillicoresLessThan": CPU_BUDGET_MILLICORES,
            "memoryMiLessThan": MEMORY_BUDGET_MI,
        },
    }
    return payload


def render_text(payload: dict[str, Any]) -> str:
    observed = payload["observed"]
    budget = payload["budget"]
    status = "passed" if payload["ok"] else "failed"
    return "\n".join(
        (
            f"resource-measurement: {status}",
            f"cpu-millicores: {observed['cpuMillicores']}",
            f"memory-mi: {observed['memoryMi']}",
            f"sample-count: {payload['sampleCount']}",
            f"budget-cpu-millicores-less-than: {budget['cpuMillicoresLessThan']}",
            f"budget-memory-mi-less-than: {budget['memoryMiLessThan']}",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check controller CPU and memory budget.")
    parser.add_argument("--sample", help="read captured kubectl top output instead of running kubectl")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--selector", default=DEFAULT_SELECTOR)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        output = read_sample(args)
        payload = build_payload(args, output)
    except (OSError, RuntimeError, ValueError) as exc:
        if args.format == "json":
            print(json.dumps({"schemaVersion": SCHEMA_VERSION, "ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print("resource-measurement: failed")
            print(f"error: {exc}")
        return 1

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
