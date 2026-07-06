#!/usr/bin/env python3
"""Verify external gate commands stay low-impact and evidence-only."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_external_gate_plan import build_plan  # noqa: E402


README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
SAFE_TOOL = "verify_external_gate_command_safety.py"

LOCAL_ALLOWED_PREFIXES = (
    ("python3", "-B", "scripts/run_lightweight_cluster_smoke.py"),
    ("python3", "-B", "scripts/run_managed_kubernetes_smoke.py"),
    ("python3", "-B", "scripts/run_helm_smoke.py"),
    ("python3", "-B", "scripts/run_krew_smoke.py"),
    ("python3", "-B", "scripts/run_admission_kind_smoke.py"),
    ("python3", "-B", "scripts/measure_controller_resources.py"),
    ("python3", "-B", "scripts/build_external_evidence.py"),
    ("python3", "-B", "bin/kube-actuary-controller", "loop"),
    ("python3", "-B", "scripts/validate_live_evidence.py"),
    ("python3", "-B", "scripts/build_live_evidence_manifest.py"),
    ("python3", "-B", "scripts/check_live_evidence_coverage.py"),
    ("python3", "-B", "scripts/build_release_evidence_directory.py"),
)
CONTROLLER_LOOP_PREFIX = ("python3", "-B", "bin/kube-actuary-controller", "loop")
BLOCKED_SHELL_TOKENS = {";", "&&", "||", "|", "<"}
REQUIRED_SNIPPETS = (
    "--dry-run=server",
    "build_external_evidence.py --kind kubectl-explain",
    "build_release_evidence_directory.py",
)


def command_entries(plan: dict[str, Any]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for gate in plan.get("gates", []):
        gate_id = gate.get("id", "unknown-gate")
        for command in gate.get("recommendedCommands", []):
            entries.append((str(gate_id), str(command)))
    for command in plan.get("closureCommands", []):
        entries.append(("closure", str(command)))
    return entries


def has_prefix(tokens: list[str], prefix: tuple[str, ...]) -> bool:
    return tokens[: len(prefix)] == list(prefix)


def parse_command(source: str, command: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if "$(" in command or "`" in command:
        errors.append(f"{source}: shell substitution is not allowed: {command}")
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return [], [f"{source}: command must parse with shlex: {exc}"]
    if not tokens:
        errors.append(f"{source}: command must not be empty")
    for token in tokens:
        if token in BLOCKED_SHELL_TOKENS:
            errors.append(f"{source}: shell control token is not allowed: {token}")
    if tokens.count(">") > 1:
        errors.append(f"{source}: only one redirect token is allowed")
    if ">" in tokens:
        redirect_index = tokens.index(">")
        if not has_prefix(tokens, CONTROLLER_LOOP_PREFIX):
            errors.append(f"{source}: only controller loop capture may redirect output")
        if redirect_index != len(tokens) - 2:
            errors.append(f"{source}: redirect must end with one output placeholder")
    return tokens, errors


def validate_kubectl(source: str, command: str, tokens: list[str]) -> list[str]:
    if len(tokens) < 2:
        return [f"{source}: kubectl command missing verb"]
    verb = tokens[1]
    if verb == "apply":
        if "--dry-run=server" not in tokens:
            return [f"{source}: kubectl apply must use --dry-run=server: {command}"]
        return []
    if verb == "explain":
        return []
    return [f"{source}: kubectl verb is not allowed in external gate commands: {verb}"]


def validate_python(source: str, command: str, tokens: list[str]) -> list[str]:
    if any(has_prefix(tokens, prefix) for prefix in LOCAL_ALLOWED_PREFIXES):
        return []
    return [f"{source}: python command is not an approved evidence helper: {command}"]


def validate_command(source: str, command: str) -> tuple[list[str], str | None]:
    tokens, errors = parse_command(source, command)
    if errors or not tokens:
        return errors, tokens[0] if tokens else None
    if tokens[0] == "kubectl":
        return validate_kubectl(source, command, tokens), "kubectl"
    if tokens[0] == "python3":
        return validate_python(source, command, tokens), "python3"
    return [f"{source}: command prefix is not allowed: {tokens[0]}"], tokens[0]


def main() -> int:
    plan = build_plan()
    entries = command_entries(plan)
    errors: list[str] = []
    kubectl_count = 0
    for source, command in entries:
        command_errors, prefix = validate_command(source, command)
        errors.extend(command_errors)
        if prefix == "kubectl":
            kubectl_count += 1

    joined_commands = "\n".join(command for _, command in entries)
    for snippet in REQUIRED_SNIPPETS:
        if snippet not in joined_commands:
            errors.append(f"external gate commands missing safety snippet: {snippet}")
    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        if SAFE_TOOL not in path.read_text():
            errors.append(f"{path.relative_to(ROOT)} missing {SAFE_TOOL}")

    if errors:
        print("external-gate-command-safety: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("external-gate-command-safety: passed")
    print(f"commands: {len(entries)}")
    print(f"kubectl: {kubectl_count}")
    print("writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
