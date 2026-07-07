#!/usr/bin/env python3
"""Verify the selected next-unblock action runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_next_unblock_action.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
TEST_PLAN = ROOT / "docs" / "test-plan-v0.2.0.md"
TEST_RESULTS = ROOT / "docs" / "test-results-v0.2.0.md"
SCHEMA = "kube-actuary.next-unblock-action-run.v1"
NEXT_SCHEMA = "kube-actuary.next-unblock-action.v1"


def run_runner(path: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(RUNNER), str(path), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_kind_env(path: Path, ok: bool) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    kind = path / "kind"
    if ok:
        kind.write_text("#!/bin/sh\necho 'kind v0.99.0-test'\nexit 0\n")
    else:
        kind.write_text("#!/bin/sh\necho 'kind is not installed in test' >&2\nexit 1\n")
    kind.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def fake_kubectl_env(path: Path) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    kubectl = path / "kubectl"
    kubectl.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"cluster-info\" ]; then\n"
        "  echo 'Kubernetes control plane is running at https://127.0.0.1:6443'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def write_next_action(path: Path, selected: dict) -> None:
    metadata = path / ".kubeactuary"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "next-unblock-action.json").write_text(
        json.dumps(
            {
                "schemaVersion": NEXT_SCHEMA,
                "sourcePlanSchema": "kube-actuary.version-unblock-plan.v1",
                "sourceWorklistQueueSource": "prepared-live-validation-queue",
                "status": "selected" if selected else "clear",
                "clusterWrites": "disabled",
                "selected": selected,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def kind_action() -> dict:
    return {
        "id": "01-missing-tool-kind",
        "kind": "missing-tool",
        "tool": "kind",
        "items": 2,
        "affectedVersions": ["Current Baseline", "0.8.0"],
        "nextStep": "install the missing tool or run the evidence capture on a host that already has it",
        "commands": {
            "verify": ["kind version"],
            "refresh": ["python3 -B scripts/prepare_live_evidence_directory.py evidence/live --probe-environment"],
            "inspect": [],
            "record": [],
        },
    }


def environment_action() -> dict:
    return {
        "id": "02-environment-cluster-unavailable",
        "kind": "environment",
        "environmentStatus": "cluster-unavailable",
        "environmentReason": "connection-refused",
        "items": 1,
        "affectedVersions": ["0.4.3"],
        "nextStep": "start or select a disposable cluster, then rerun the probe",
        "commands": {
            "verify": ["kubectl cluster-info --request-timeout=5s"],
            "refresh": [],
            "inspect": [],
            "record": [],
        },
    }


def parse_stdout_json(label: str, result: subprocess.CompletedProcess[str], errors: list[str]) -> dict:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"{label} JSON must parse: {exc}: {result.stdout[:200]}")
        return {}


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        good_dir = tmpdir / "good"
        blocked_dir = tmpdir / "blocked"
        environment_dir = tmpdir / "environment"
        unsafe_dir = tmpdir / "unsafe"
        clear_dir = tmpdir / "clear"
        unprepared_dir = tmpdir / "unprepared"
        write_next_action(good_dir, kind_action())
        write_next_action(blocked_dir, kind_action())
        write_next_action(environment_dir, environment_action())
        write_next_action(
            unsafe_dir,
            {
                **kind_action(),
                "commands": {"verify": ["kubectl apply -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"]},
            },
        )
        write_next_action(clear_dir, {})

        unprepared = run_runner(unprepared_dir)
        plan = run_runner(good_dir)
        plan_markdown = run_runner(good_dir, "--format", "markdown")
        passed = run_runner(good_dir, "--run", "--format", "json", env=fake_kind_env(tmpdir / "kind-ok", ok=True))
        blocked = run_runner(blocked_dir, "--run", "--format", "json", env=fake_kind_env(tmpdir / "kind-fail", ok=False))
        blocked_text = run_runner(blocked_dir, "--run", env=fake_kind_env(tmpdir / "kind-fail-2", ok=False))
        blocked_record = run_runner(
            blocked_dir,
            "--run",
            "--record",
            "--format",
            "json",
            env=fake_kind_env(tmpdir / "kind-fail-record", ok=False),
        )
        environment_passed = run_runner(
            environment_dir,
            "--run",
            "--format",
            "json",
            env=fake_kubectl_env(tmpdir / "kubectl-ok"),
        )
        unsafe = run_runner(unsafe_dir)
        clear = run_runner(clear_dir, "--run", "--format", "json")

        if unprepared.returncode == 0:
            errors.append("runner must fail for an unprepared evidence directory")
        if "prepare_live_evidence_directory.py" not in unprepared.stdout:
            errors.append("unprepared runner error must include prepare command")
        if plan.returncode != 0:
            errors.append(f"runner plan failed: {plan.stderr.strip() or plan.stdout.strip()}")
        for snippet in (
            "next-unblock-action-run: plan",
            "queue-source: prepared-live-validation-queue",
            "target: kind",
            "valid-commands: 1",
            "ran: 0",
        ):
            if snippet not in plan.stdout:
                errors.append(f"runner plan text must include: {snippet}")
        for snippet in (
            "# KubeActuary Next Unblock Action Run",
            "Mode: `plan`",
            "Status: `plan`",
            "## Commands",
        ):
            if snippet not in plan_markdown.stdout:
                errors.append(f"runner Markdown plan must include: {snippet}")
        if passed.returncode != 0:
            errors.append(f"runner success case failed: {passed.stderr.strip() or passed.stdout.strip()}")
            passed_payload = {}
        else:
            passed_payload = parse_stdout_json("passed runner", passed, errors)
        if passed_payload.get("schemaVersion") != SCHEMA:
            errors.append("runner schemaVersion mismatch")
        if passed_payload.get("status") != "passed" or passed_payload.get("summary", {}).get("ran") != 1:
            errors.append("runner success case must run one verifier and pass")
        if passed_payload.get("clusterWrites") != "disabled":
            errors.append("runner must keep cluster writes disabled")
        if blocked.returncode == 0:
            errors.append("runner blocked case must return non-zero")
            blocked_payload = {}
        else:
            blocked_payload = parse_stdout_json("blocked runner", blocked, errors)
        if blocked_payload.get("status") != "blocked" or blocked_payload.get("summary", {}).get("failed") != 1:
            errors.append("runner blocked case must preserve blocked status")
        if (blocked_payload.get("failure") or {}).get("message") != "kind is not installed in test":
            errors.append("runner blocked case must preserve verifier failure message")
        if "blocker: kind is not installed in test" not in blocked_text.stdout:
            errors.append("runner text must print blocker summary")
        if blocked_record.returncode == 0:
            errors.append("runner recorded blocked case must return non-zero")
        record_json = blocked_dir / ".kubeactuary" / "next-unblock-action-run.json"
        record_md = blocked_dir / ".kubeactuary" / "next-unblock-action-run.md"
        if not record_json.is_file() or not record_md.is_file():
            errors.append("runner --record must persist JSON and Markdown reports")
        else:
            record_payload = json.loads(record_json.read_text())
            if record_payload.get("status") != "blocked":
                errors.append("runner recorded JSON must preserve blocked status")
            if "kind is not installed in test" not in record_md.read_text():
                errors.append("runner recorded Markdown must preserve blocker message")
        if environment_passed.returncode != 0:
            errors.append(f"environment verifier should pass with fake kubectl: {environment_passed.stderr.strip() or environment_passed.stdout.strip()}")
        else:
            environment_payload = parse_stdout_json("environment runner", environment_passed, errors)
            if environment_payload.get("status") != "passed":
                errors.append("environment runner must support cluster-info verifier")
        if unsafe.returncode == 0:
            errors.append("unsafe verifier command must fail validation")
        if "verify command is not in the next-unblock allowlist" not in unsafe.stdout:
            errors.append("unsafe verifier command must explain allowlist failure")
        if clear.returncode != 0:
            errors.append(f"clear next-unblock action should return zero: {clear.stderr.strip() or clear.stdout.strip()}")
        clear_payload = parse_stdout_json("clear runner", clear, errors)
        if clear_payload.get("status") != "clear" or clear_payload.get("summary", {}).get("commands") != 0:
            errors.append("clear next-unblock action must report clear status with zero commands")

    required_snippets = {
        README: ("run_next_unblock_action.py", "kube-actuary.next-unblock-action-run.v1"),
        README_KO: ("run_next_unblock_action.py", "kube-actuary.next-unblock-action-run.v1"),
        LIVE_VALIDATION: ("run_next_unblock_action.py", "next-unblock-action-run.json"),
        TASKBOARD: ("Next unblock action runner", "verify_next_unblock_action_runner.py"),
        TEST_PLAN: ("verify_next_unblock_action_runner.py", "next unblock action runner"),
        TEST_RESULTS: ("verify_next_unblock_action_runner.py", "next unblock action runner"),
    }
    for path, snippets in required_snippets.items():
        text = path.read_text()
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} must document {snippet}")

    if errors:
        print("next-unblock-action-runner: failed")
        for error in errors:
            print(f"error: {error}")
        return 1
    print("next-unblock-action-runner: passed")
    print("mode: plan,run")
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
