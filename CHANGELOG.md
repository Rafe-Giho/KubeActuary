# Changelog

## 0.2.0 - Unreleased

Evidence collector release:

- add `collect dry-run` for server-side dry-run evidence;
- add `collect diff` with Kubernetes diff exit-code handling;
- add `collect rollback` for explicit rollback command or manifest evidence;
- add `collect health-plan` for declared post-change checks;
- add `validate` for local capsule structure checks;
- add `doctor` for local runtime and kubectl client diagnostics;
- normalize collector failure summaries with stable reason fields;
- add deterministic `digest` output for capsule specs;
- add `help` topics and agent-readable JSON help;
- version the structured help contract with compatibility fields;
- add local release taskboard and repeatable release verification script;
- add GitHub Actions CI for the local verification suite;
- add release checklist and generated release notes dry-run tooling;
- render CRD objects with capsule digest annotations, post-checks, and richer
  evidence summaries;
- render CRD status fields and condition mappings for local capsule state;
- add Kubernetes and managed-service compatibility notes plus offline CRD smoke;
- add CRD upgrade and rollback fixtures with an offline verifier;
- add CRD OpenAPI descriptions and kubectl explain quality checks;
- add a pure low-overhead controller reconcile model and watch boundary checks;
- add namespace-scoped and cluster-scoped controller RBAC manifests with
  status-only permission checks;
- add controller health, readiness, metrics, and leader-election runtime
  contracts;
- add controller resource-budget contract and kubectl-top measurement harness;
- add lightweight cluster smoke plan harness for kind, minikube, MicroK8s, and
  k3s;
- add Helm chart seed with CRD packaging and optional controller RBAC;
- add Kustomize base and controller RBAC overlays with render verification;
- add multi-target release archive packager with SHA-256 and install smoke
  verification;
- add Krew manifest generator and offline manifest verifier;
- add deterministic SBOM and SLSA-style provenance generators with verifier;
- add air-gapped install manifest generator and offline bundle verifier;
- add Kyverno policy evidence adapter with pass/fail fixtures;
- add OPA/Rego policy evidence adapter with pass/fail fixtures;
- add kube-linter policy evidence adapter with pass/fail fixtures;
- add kube-score policy evidence adapter with pass/fail fixtures;
- add v0.2 tests, docs, and examples.

## 0.1.0

Initial alpha scope:

- local `OperationCapsule` JSON workflow;
- `draft`, `inspect`, `attach-evidence`, `collect auth`, `verify`, `gate`,
  `render-crd`, and `demo` commands;
- kubectl plugin entrypoint;
- JSON Schema;
- CRD seed;
- examples;
- test suite.
