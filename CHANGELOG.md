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
- add versioned release progress reports for local task tracking;
- add version-grouped worklist generation with version/open-only filters for
  open task, capture status, and evidence file readiness;
- add local version iteration packs for repeated per-version verification with
  evidence readiness;
- add local version iteration diffs for comparing repeated verification runs;
- add local version iteration history recording for run-to-run evidence
  tracking;
- add local version iteration history inspection for latest-run evidence status
  checks;
- add deterministic next-task selection from version worklists;
- add evidence-aware next-task selection that skips completed local evidence files;
- make evidence-aware worklists and next-task selection prefer prepared live
  validation queues when an evidence directory already has one;
- preserve blocker summaries and drilldown commands in version iteration packs;
- surface the worklist queue source in Markdown/text next-task outputs;
- surface missing tools and next steps in version worklist Markdown;
- show all blocker summaries in version worklist Markdown;
- show filtered worklist commands for version worklist blockers;
- show version-scoped blocker drilldown commands in version worklist Markdown;
- summarize repeated missing-tool and environment blockers in version worklist
  reports;
- add capture-status, missing-tool, and environment-status filters to version
  worklists, iteration packs, iteration history, and next-task selection;
- pass blocker-focused filters through live evidence scaffolds and version
  iteration advance records;
- preserve prepared queue source on probe-generated live evidence next-task
  artifacts;
- preserve prepared queue source in version iteration packs;
- preserve prepared queue source in version iteration history records and status;
- show latest blocker summaries and drilldowns in version iteration history status;
- show latest run filters in version iteration history status;
- show the selected latest next task in version iteration history status;
- add Markdown output for version iteration history status;
- add recorded version iteration history status reports;
- show latest environment probe failures in version iteration history status;
- show latest run diff summaries in version iteration history status;
- show latest per-version diff summaries in version iteration history status;
- show latest run, worklist, and diff artifact paths in version iteration
  history status;
- show next local loop commands in version iteration history status;
- show latest next-task evidence file details in version iteration history status;
- show latest next-task worklist drilldowns in version iteration history status;
- preserve prepared queue source in next-task runner and advance reports;
- preserve environment blocker status and next steps in advance reports;
- surface runner and advance queue source in release evidence status/progress;
- infer prepared queue source for older evidence status records when a live
  validation queue is present;
- report queue-source origin so explicit and inferred release evidence status
  metadata stays distinguishable;
- report next-task versus live-queue consistency in release evidence
  status/progress;
- report runner and advance record consistency against the current next-task
  artifact in release evidence status/progress;
- add tool-ready and missing-tool next actions to release progress reports;
- show all open items per version in release progress Markdown;
- show all action blockers in release progress Markdown;
- show filtered worklist commands for release progress blockers;
- show all tool-ready actions and evidence next commands in release progress
  Markdown;
- show selected next-task file details and commands in release progress Markdown;
- summarize repeated missing-tool and environment blockers in release progress
  reports;
- surface selected next-task, runner, environment, and advance status in release
  progress Markdown for local evidence directories;
- show version-iteration advance run id and history run count in release
  progress Markdown;
- preserve selected next-task runner failure reasons in release evidence status
  and progress output;
- show all release evidence status next commands, next-task files, and
  next-task commands;
- show selected next-task worklist drilldowns in release evidence status;
- show filtered worklist commands for release evidence status blockers;
- add CLI Markdown output for release evidence status inspection;
- add CLI Markdown output for version iteration advance reports;
- show selected next-task worklist drilldowns in version iteration advance
  reports;
- add CLI Markdown output for selected next-task runner reports;
- add CLI Markdown output for next-task evidence build reports;
- record next-task evidence build status under prepared evidence directories;
- recommend environment probing before further live capture when a runner fails
  before any probe has run;
- surface selected environment-blocker next steps in release evidence status
  and progress output;
- use persisted live validation queues as the release progress next-action
  source for prepared evidence directories;
- record zero-run blocked runner status during probe-blocked version
  iteration advance;
- record a blocked history snapshot as the latest run during probe-blocked
  version iteration advance;
- prioritize resolved prepared-queue commands in release evidence status
  next-command output;
- limit release evidence next-command output to tool-ready commands, keeping
  missing-tool and environment-blocked actions in blocker summaries;
- limit release progress next-action runnable commands to tool-ready actions;
- add external verification gate plan generation for remaining live evidence;
- add external gate command safety verification for generated dry-run,
  read-only, and evidence-only commands;
- add external gate evidence evaluation against captured smoke manifests and
  supplemental evidence;
- add supplemental external evidence builder for raw live outputs;
- add external evidence bundle generation for auditable closure artifacts;
- add release evidence directory builder for repeated local evidence closure;
- keep generated `.kubeactuary` metadata out of release evidence directory
  scans even with custom output directories;
- add release evidence status inspector for partial evidence directories;
- surface selected runner status from release evidence directory inspection;
- surface environment probe and blocker metadata from release evidence status;
- surface version iteration advance status from release evidence inspection;
- add opt-in release evidence status recording under prepared evidence
  directories;
- add local next-task evidence builder for prepared evidence directories;
- add selected next-version task runner for plan-by-default evidence command
  execution;
- report actionable prepare commands when selected next-task artifacts are
  missing from an evidence directory;
- add selected next-version task runner failure summaries to text, JSON, and
  recorded Markdown output;
- keep selected next-version task runner execution at zero runs when the
  prepared task is blocked by environment or missing tools;
- add opt-in next-version task runner recording under prepared evidence
  directories;
- add version iteration advance workflow for selected-task execution plus
  before/after history recording;
- record version iteration advance workflow status under prepared evidence
  directories;
- record selected runner status from version iteration advance runs;
- add probe-aware live evidence directory and iteration advance status for
  unavailable cluster environments;
- add local environment probe reports for prepared evidence directories;
- add local environment blocker reports for prepared evidence directories;
- report missing local evidence directories as `not-prepared` in release
  progress instead of failing the task loop;
- add clean-artifact verification for generated Python cache files and ignored
  local evidence state;
- add live validation queue generation with ordered external evidence commands,
  optional environment blockers, and deterministic evidence-directory paths;
- add live validation queue command safety verification for placeholder and
  resolved evidence commands;
- add live evidence directory scaffold generation for repeated external
  evidence capture with next-task advancement;
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
- add controller resource-budget contract and kubectl-top measurement harness
  with structured JSON evidence output;
- add read-only controller resource-budget capture helper for live evidence
  directories;
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
- add gate-level tool readiness inventory for live validation planning;
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
