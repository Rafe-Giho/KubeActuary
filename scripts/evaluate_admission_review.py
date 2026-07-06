#!/usr/bin/env python3
"""Evaluate KubeActuary admission policy for a captured AdmissionReview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_WRITER_GROUP = "kubeactuary.dev/ai-writers"
AI_SERVICEACCOUNT_NAMESPACE = "ai-agents"
CAPSULE_ANNOTATION = "kubeactuary.dev/capsule"
DIGEST_ANNOTATION = "kubeactuary.dev/capsule-digest"
REQUIRED_ANNOTATIONS = (CAPSULE_ANNOTATION, DIGEST_ANNOTATION)
WRITE_OPERATIONS = {"CREATE", "UPDATE", "PATCH", "DELETE"}


def request(review: dict[str, Any]) -> dict[str, Any]:
    value = review.get("request")
    return value if isinstance(value, dict) else {}


def annotations(admission_request: dict[str, Any]) -> dict[str, str]:
    obj = admission_request.get("object")
    if not isinstance(obj, dict):
        obj = admission_request.get("oldObject")
    if not isinstance(obj, dict):
        return {}
    metadata = obj.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    value = metadata.get("annotations")
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def is_ai_identity(admission_request: dict[str, Any]) -> bool:
    user_info = admission_request.get("userInfo")
    if not isinstance(user_info, dict):
        return False
    username = str(user_info.get("username", ""))
    groups = {str(group) for group in user_info.get("groups", []) if isinstance(group, str)}
    return (
        AI_WRITER_GROUP in groups
        or username.startswith(f"system:serviceaccount:{AI_SERVICEACCOUNT_NAMESPACE}:")
    )


def missing_required_annotations(admission_request: dict[str, Any]) -> list[str]:
    found = annotations(admission_request)
    return [key for key in REQUIRED_ANNOTATIONS if not found.get(key)]


def decision(review: dict[str, Any]) -> dict[str, Any]:
    admission_request = request(review)
    uid = str(admission_request.get("uid", ""))
    operation = str(admission_request.get("operation", "")).upper()
    if operation not in WRITE_OPERATIONS:
        return {"uid": uid, "allowed": True, "reason": "non-write-operation"}
    if not is_ai_identity(admission_request):
        return {"uid": uid, "allowed": True, "reason": "identity-not-selected"}

    missing = missing_required_annotations(admission_request)
    if missing:
        return {
            "uid": uid,
            "allowed": False,
            "reason": "missing-kubeactuary-annotations",
            "missingAnnotations": missing,
        }
    return {"uid": uid, "allowed": True, "reason": "annotations-present"}


def admission_response(review: dict[str, Any]) -> dict[str, Any]:
    result = decision(review)
    admission_request = request(review)
    found_annotations = annotations(admission_request)
    allowed = bool(result.get("allowed"))
    response = {
        "uid": result.get("uid", ""),
        "allowed": allowed,
        "status": {
            "reason": result.get("reason", "unknown"),
        },
        "auditAnnotations": {
            "kubeactuary.dev/decision": "allow" if allowed else "deny",
            "kubeactuary.dev/reason": str(result.get("reason", "unknown")),
        },
    }
    capsule = found_annotations.get(CAPSULE_ANNOTATION)
    digest = found_annotations.get(DIGEST_ANNOTATION)
    if capsule:
        response["auditAnnotations"]["kubeactuary.dev/capsule"] = capsule
    if digest:
        response["auditAnnotations"]["kubeactuary.dev/capsule-digest"] = digest
    if result.get("missingAnnotations"):
        response["status"]["message"] = "missing required KubeActuary annotations"
        response["auditAnnotations"]["kubeactuary.dev/missing-annotations"] = ",".join(result["missingAnnotations"])
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": response,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate KubeActuary admission review policy.")
    parser.add_argument("input")
    parser.add_argument("--out", default="-")
    parser.add_argument("--response", action="store_true", help="emit an AdmissionReview response with audit annotations")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text())
    if not isinstance(payload, dict):
        raise SystemExit("AdmissionReview JSON root must be an object")
    result = decision(payload)
    output = admission_response(payload) if args.response else result
    text = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        Path(args.out).write_text(text)
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
