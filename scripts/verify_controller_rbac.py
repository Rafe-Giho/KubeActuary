#!/usr/bin/env python3
"""Verify optional controller RBAC manifests stay low privilege."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAMESPACE_RBAC = ROOT / "deploy" / "controller" / "namespace-scoped-rbac.yaml"
CLUSTER_RBAC = ROOT / "deploy" / "controller" / "cluster-scoped-rbac.yaml"

MAIN_RESOURCE = "operationcapsules"
STATUS_RESOURCE = "operationcapsules/status"
READ_VERBS = ("get", "list", "watch")
STATUS_VERBS = ("get", "patch", "update")
FORBIDDEN_VERBS = ("*", "create", "delete", "deletecollection")
FORBIDDEN_RESOURCES = ("*", "pods", "deployments", "events", "nodes", "secrets", "configmaps")


def quoted_list(items: tuple[str, ...]) -> str:
    return ", ".join(f'"{item}"' for item in items)


def rule_verbs(text: str, resource: str) -> list[tuple[str, ...]]:
    pattern = re.compile(
        r'- apiGroups: \["ops\.kubeactuary\.dev"\]\n'
        rf'\s+resources: \["{re.escape(resource)}"\]\n'
        r'\s+verbs: \[(.*?)\]'
    )
    rules = []
    for match in pattern.finditer(text):
        verbs = tuple(item.strip().strip('"') for item in match.group(1).split(","))
        rules.append(verbs)
    return rules


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def verify_manifest(path: Path, mode: str, errors: list[str]) -> None:
    text = path.read_text()
    require("kind: ServiceAccount" in text, f"{mode}: missing ServiceAccount", errors)
    require("name: kubeactuary-controller" in text, f"{mode}: missing controller name", errors)
    require("namespace: kubeactuary-system" in text, f"{mode}: missing controller namespace", errors)

    if mode == "namespace":
        require("kind: Role" in text, "namespace: missing Role", errors)
        require("kind: RoleBinding" in text, "namespace: missing RoleBinding", errors)
        require("kind: ClusterRole" not in text, "namespace: must not include ClusterRole", errors)
        require("kind: ClusterRoleBinding" not in text, "namespace: must not include ClusterRoleBinding", errors)
        require("roleRef:\n  apiGroup: rbac.authorization.k8s.io\n  kind: Role" in text, "namespace: RoleBinding must reference Role", errors)
    else:
        require("kind: ClusterRole" in text, "cluster: missing ClusterRole", errors)
        require("kind: ClusterRoleBinding" in text, "cluster: missing ClusterRoleBinding", errors)
        require("roleRef:\n  apiGroup: rbac.authorization.k8s.io\n  kind: ClusterRole" in text, "cluster: ClusterRoleBinding must reference ClusterRole", errors)

    main_rules = rule_verbs(text, MAIN_RESOURCE)
    status_rules = rule_verbs(text, STATUS_RESOURCE)
    require(main_rules == [READ_VERBS], f"{mode}: main resource verbs must be [{quoted_list(READ_VERBS)}]", errors)
    require(status_rules == [STATUS_VERBS], f"{mode}: status resource verbs must be [{quoted_list(STATUS_VERBS)}]", errors)

    for verb in FORBIDDEN_VERBS:
        require(f'"{verb}"' not in text, f"{mode}: forbidden verb present: {verb}", errors)
    for resource in FORBIDDEN_RESOURCES:
        require(f'resources: ["{resource}"]' not in text, f"{mode}: forbidden resource present: {resource}", errors)
    require('apiGroups: ["*"]' not in text, f"{mode}: wildcard apiGroup present", errors)


def main() -> int:
    errors: list[str] = []
    verify_manifest(NAMESPACE_RBAC, "namespace", errors)
    verify_manifest(CLUSTER_RBAC, "cluster", errors)

    if errors:
        print("controller-rbac: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-rbac: passed")
    print("namespace-mode: Role/RoleBinding")
    print("cluster-mode: ClusterRole/ClusterRoleBinding")
    print(f"read-only: {MAIN_RESOURCE}")
    print(f"status-write-only: {STATUS_RESOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
