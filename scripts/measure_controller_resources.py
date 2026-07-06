#!/usr/bin/env python3
"""Measure or evaluate controller resource usage against the v0.4.3 budget."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


CPU_BUDGET_MILLICORES = 50
MEMORY_BUDGET_MI = 64
DEFAULT_NAMESPACE = "kubeactuary-system"
DEFAULT_SELECTOR = "app.kubernetes.io/name=kubeactuary,app.kubernetes.io/component=controller"


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


def parse_top_output(output: str) -> tuple[int, int]:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check controller CPU and memory budget.")
    parser.add_argument("--sample", help="read captured kubectl top output instead of running kubectl")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--selector", default=DEFAULT_SELECTOR)
    args = parser.parse_args(argv)

    try:
        output = read_sample(args)
        cpu_m = parse_top_output(output)[0]
        memory_mi = parse_top_output(output)[1]
    except (OSError, RuntimeError, ValueError) as exc:
        print("resource-measurement: failed")
        print(f"error: {exc}")
        return 1

    ok = cpu_m < CPU_BUDGET_MILLICORES and memory_mi < MEMORY_BUDGET_MI
    print("resource-measurement: passed" if ok else "resource-measurement: failed")
    print(f"cpu-millicores: {cpu_m}")
    print(f"memory-mi: {memory_mi}")
    print(f"budget-cpu-millicores-less-than: {CPU_BUDGET_MILLICORES}")
    print(f"budget-memory-mi-less-than: {MEMORY_BUDGET_MI}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
