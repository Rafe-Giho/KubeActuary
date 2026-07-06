#!/usr/bin/env python3
"""Verify optional admission webhook prototype manifest."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "deploy" / "admission" / "validatingwebhookconfiguration.yaml"
DOC = ROOT / "docs" / "admission.md"


def main() -> int:
    errors: list[str] = []
    text = MANIFEST.read_text() if MANIFEST.is_file() else ""
    doc = DOC.read_text() if DOC.is_file() else ""

    required = (
        "apiVersion: admissionregistration.k8s.io/v1",
        "kind: ValidatingWebhookConfiguration",
        "failurePolicy: Ignore",
        "sideEffects: None",
        "timeoutSeconds: 2",
        "kubeactuary.dev/admission: enabled",
        "operations:",
        "- CREATE",
        "- UPDATE",
        "- PATCH",
        "- DELETE",
        "service:",
        "path: /validate",
    )
    for value in required:
        if value not in text:
            errors.append(f"manifest missing: {value}")

    forbidden = ("failurePolicy: Fail", "reinvocationPolicy", "kubectl apply")
    for value in forbidden:
        if value in text:
            errors.append(f"manifest must not include: {value}")

    for value in ("failurePolicy: Ignore", "namespace opt-in", "kind smoke remains"):
        if value not in doc:
            errors.append(f"admission docs missing: {value}")

    kind = shutil.which("kind")
    if kind is None:
        live_status = "kind-unavailable"
    else:
        live_status = "kind-available"

    if errors:
        print("admission-webhook: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-webhook: passed")
    print("failurePolicy: Ignore")
    print(f"kind-smoke: {live_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
