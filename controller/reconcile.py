"""Pure OperationCapsule reconcile model.

This module intentionally has no Kubernetes client dependency. It computes the
status a low-overhead controller would patch after watching only
OperationCapsule resources.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


CONDITION_TYPES = ("EvidenceComplete", "GateOpen", "Blocked", "RollbackReady", "Expired")
WATCH_RESOURCE = "operationcapsules.ops.kubeactuary.dev"


def canonical_digest(document: dict[str, Any]) -> str:
    payload = {
        "apiVersion": document.get("apiVersion"),
        "kind": document.get("kind"),
        "metadata": {"name": document.get("metadata", {}).get("name")},
        "spec": document.get("spec", {}),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def evidence_records(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in document.get("spec", {}).get("evidence", []):
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            records[record["id"]] = record
    return records


def evidence_gaps(document: dict[str, Any]) -> tuple[list[str], list[str]]:
    required = [
        evidence_id
        for evidence_id in document.get("spec", {}).get("requiredEvidence", [])
        if isinstance(evidence_id, str)
    ]
    attached = evidence_records(document)
    missing = [evidence_id for evidence_id in required if evidence_id not in attached]
    failed = [evidence_id for evidence_id in required if attached.get(evidence_id, {}).get("ok") is False]
    return missing, failed


def rollback_ready(document: dict[str, Any]) -> bool:
    rollback = document.get("spec", {}).get("rollback", {})
    if not rollback.get("required"):
        return True
    return bool(
        rollback.get("provided")
        or rollback.get("command")
        or rollback.get("manifestRef")
        or rollback.get("manifestSha256")
    )


def condition(condition_type: str, status: bool, reason: str, message: str) -> dict[str, str]:
    return {
        "type": condition_type,
        "status": "True" if status else "False",
        "reason": reason,
        "message": message,
    }


def reconcile_status(document: dict[str, Any]) -> dict[str, Any]:
    missing, failed = evidence_gaps(document)
    records = evidence_records(document)
    evidence_complete = not missing and not failed
    blocked = bool(failed)
    rollback_is_ready = rollback_ready(document)
    expired = False
    gate_open = evidence_complete and rollback_is_ready and not blocked and not expired

    if expired:
        phase = "Expired"
    elif gate_open:
        phase = "GateOpen"
    elif blocked:
        phase = "Blocked"
    elif records:
        phase = "EvidenceAttached"
    else:
        phase = "Drafted"

    return {
        "phase": phase,
        "gate": "Open" if gate_open else "Closed",
        "missingEvidence": missing,
        "failedEvidence": failed,
        "digest": canonical_digest(document),
        "conditions": [
            condition(
                "EvidenceComplete",
                evidence_complete,
                "AllEvidencePresent" if evidence_complete else "EvidenceMissingOrFailed",
                "all required evidence is present and successful"
                if evidence_complete
                else "required evidence is missing or failed",
            ),
            condition(
                "GateOpen",
                gate_open,
                "GateOpen" if gate_open else "GateClosed",
                "capsule is an execution candidate" if gate_open else "capsule is not an execution candidate",
            ),
            condition(
                "Blocked",
                blocked,
                "FailedEvidencePresent" if blocked else "NoFailedEvidence",
                "one or more required evidence records failed" if blocked else "no failed required evidence",
            ),
            condition(
                "RollbackReady",
                rollback_is_ready,
                "RollbackProvided" if rollback_is_ready else "RollbackMissing",
                "rollback evidence is available or not required"
                if rollback_is_ready
                else "rollback evidence is required but missing",
            ),
            condition("Expired", expired, "NotExpired", "no expiry policy has elapsed"),
        ],
    }


def status_patch(document: dict[str, Any]) -> dict[str, Any]:
    return {"status": reconcile_status(document)}


def operationcapsule_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    items = document.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return [document]


def object_identity(document: dict[str, Any]) -> tuple[str, str | None]:
    metadata = document.get("metadata", {})
    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("OperationCapsule metadata.name is required")
    namespace = metadata.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        namespace = None
    return name, namespace


def status_patch_command(document: dict[str, Any], kubectl: str = "kubectl") -> list[str]:
    name, namespace = object_identity(document)
    patch = json.dumps(status_patch(document), sort_keys=True, separators=(",", ":"))
    command = [
        kubectl,
        "patch",
        WATCH_RESOURCE,
        name,
        "--type",
        "merge",
        "--subresource",
        "status",
        "-p",
        patch,
    ]
    if namespace:
        command.extend(["-n", namespace])
    return command


def status_patch_plan(document: dict[str, Any], kubectl: str = "kubectl") -> dict[str, Any]:
    patches = []
    for item in operationcapsule_items(document):
        name, namespace = object_identity(item)
        patches.append(
            {
                "name": name,
                "namespace": namespace,
                "resource": WATCH_RESOURCE,
                "patch": status_patch(item),
                "command": status_patch_command(item, kubectl=kubectl),
            }
        )
    return {
        "writeExecution": "disabled",
        "patches": patches,
        "count": len(patches),
    }


def watch_command(namespace: str | None = None) -> list[str]:
    command = ["kubectl", "get", WATCH_RESOURCE, "-o", "json", "--watch"]
    if namespace:
        command.extend(["-n", namespace])
    else:
        command.append("--all-namespaces")
    return command
