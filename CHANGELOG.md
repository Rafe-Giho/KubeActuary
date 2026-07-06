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
- add release taskboard audit for status and verification-count drift;
- add external verification gate plan generation for remaining live evidence;
- add external gate evidence evaluation against captured smoke manifests and
  supplemental evidence;
- add supplemental external evidence builder for raw live outputs;
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
- add optional controller runtime Deployment seed and verifier;
- add controller status patch planner with status-only verifier;
- add read-only controller sync planning with disabled write execution;
- add controller status patch dry-run helper with explicit status-only execute mode;
- add controller status loop dry-run helper for repeated read/status-patch ticks;
- add controller resource-budget contract and kubectl-top measurement harness;
- add lightweight cluster smoke plan harness for kind, minikube, MicroK8s, and
  k3s with JSON evidence output for live runs;
- add Helm chart seed with CRD packaging, optional controller RBAC, and dry-run
  smoke evidence output;
- add Kustomize base and controller RBAC overlays with render verification;
- add multi-target release archive packager with SHA-256 and install smoke
  verification;
- add Krew manifest generator, isolated install smoke harness, and offline
  manifest verifier;
- add deterministic SBOM and SLSA-style provenance generators with verifier;
- add air-gapped install manifest generator and offline bundle verifier;
- add Kyverno policy evidence adapter with pass/fail fixtures;
- add OPA/Rego policy evidence adapter with pass/fail fixtures;
- add kube-linter policy evidence adapter with pass/fail fixtures;
- add kube-score policy evidence adapter with pass/fail fixtures;
- add Pluto deprecated API evidence adapter with pass/fail fixtures;
- add common adapter evidence contract and normalized severity verification;
- add safe stdlib MCP/JSON-RPC wrapper for draft, inspect, attach, verify, and gate;
- add dedicated agent help contract verifier for schema compatibility;
- add local CI and Codex agent workflow runbooks with verifier;
- add MCP client config example and docs verifier;
- add explicit disabled-execute verifier for CLI and MCP surfaces;
- add optional admission webhook prototype manifest with offline verifier;
- add AI identity selector and required admission annotation allow/deny fixtures;
- add admission capsule digest and gate tamper fixtures;
- add admission audit annotation fixtures and incident runbook;
- add AdmissionReview response builder with audit annotation verifier;
- add local admission HTTP server with verifier;
- add optional admission kind smoke harness with dry-run evidence output;
- add upstream Kubernetes N/N-1/N-2 conformance suite seed;
- add managed Kubernetes smoke harness for EKS, GKE, and AKS evidence output;
- add security policy, threat model, and disclosure verifier;
- add API freeze contract and additive compatibility verifier;
- add documentation freeze and public examples verifier;
- add live validation readiness ledger for external evidence gates;
- add live evidence JSON validator for captured smoke reports;
- add live evidence manifest builder for captured smoke reports;
- add live evidence coverage checks for release-gate provider evidence;
- add contribution policy, NOTICE, and project governance verifier;
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
