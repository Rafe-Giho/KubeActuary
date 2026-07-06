#!/usr/bin/env python3
"""Verify the local AdmissionReview server without Kubernetes."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "kube_actuary_admission_server.py"
EVALUATOR = ROOT / "scripts" / "evaluate_admission_review.py"
FIXTURE = ROOT / "tests" / "fixtures" / "admission" / "allow-ai-annotated.json"
DOC = ROOT / "docs" / "admission.md"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int) -> None:
    deadline = time.time() + 5
    url = f"http://127.0.0.1:{port}/healthz"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("admission server did not become healthy")


def post_review(port: int) -> dict:
    payload = FIXTURE.read_bytes()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/validate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def response_contract() -> dict:
    result = subprocess.run(
        [sys.executable, "-B", str(EVALUATOR), str(FIXTURE), "--response"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def main() -> int:
    errors: list[str] = []
    http_smoke = "not-run"
    config = subprocess.run(
        [sys.executable, "-B", str(SERVER), "--print-config"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if config.returncode != 0:
        errors.append(f"server config failed: {config.stderr.strip()}")
    else:
        payload = json.loads(config.stdout)
        if payload.get("clusterAccess") != "none":
            errors.append("server config must not require cluster access")
        if payload.get("writeExecution") != "disabled":
            errors.append("server config must keep write execution disabled")

    process = None
    try:
        port = free_port()
        process = subprocess.Popen(
            [sys.executable, "-B", str(SERVER), "--port", str(port)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        wait_for_health(port)
        review = post_review(port)
        http_smoke = "passed"
    except PermissionError:
        review = response_contract()
        http_smoke = "skipped-bind-permission"
    try:
        response = review.get("response", {})
        if response.get("allowed") is not True:
            errors.append("valid annotated fixture should be allowed")
        annotations = response.get("auditAnnotations", {})
        if annotations.get("kubeactuary.dev/decision") != "allow":
            errors.append("response missing allow audit annotation")
    except Exception as exc:
        errors.append(str(exc))
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    doc = DOC.read_text()
    for snippet in ("kube_actuary_admission_server.py", "/validate", "/healthz", "verify_admission_server.py", "bind"):
        if snippet not in doc:
            errors.append(f"admission docs missing server contract: {snippet}")

    if errors:
        print("admission-server: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-server: passed")
    print("endpoint: /validate")
    print(f"http-smoke: {http_smoke}")
    print("cluster-access: none")
    print("write-execution: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
