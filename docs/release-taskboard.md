# KubeActuary Release Taskboard

This file is the local source of truth for work from the current v0.2 alpha line
to v1.0.0. Keep each task small enough to implement and verify independently.

Status legend:

- `DONE`: implemented and verified.
- `VERIFY`: implemented but needs release verification on the target matrix.
- `DOING`: actively being implemented.
- `TODO`: not started.
- `BLOCKED`: blocked by an explicit external decision or dependency.

## Current Baseline

| Area | State | Evidence |
| --- | --- | --- |
| Local CLI and capsule workflow | DONE | `python3 -B -m unittest discover -s tests` |
| v0.2 evidence collectors | DONE | `python3 -B scripts/verify_release.py --version 0.2.0` |
| Local capsule validation | DONE | `kube-actuary validate` unit tests and release suite check |
| Local diagnostics | DONE | `kube-actuary doctor` fake tool-path tests and release suite check |
| Collector failure contract | DONE | stable summary prefix and reason-field unit tests |
| GitHub Actions CI | DONE | workflow YAML parse and release verification command |
| Release checklist and notes | DONE | release checklist doc plus generated notes dry-run |
| Release taskboard audit | DONE | `scripts/verify_release_taskboard.py` verifies statuses, remaining evidence notes, and release check count |
| Release progress | DONE | `scripts/verify_release_progress.py` verifies JSON/Markdown/text versioned release progress reporting plus evidence-directory queue-source status |
| Version worklist | DONE | `scripts/generate_version_worklist.py`, `scripts/prepare_version_iteration.py`, `scripts/compare_version_iterations.py`, `scripts/record_version_iteration.py`, `scripts/inspect_version_history.py`, `scripts/select_next_version_task.py`, and `scripts/verify_version_worklist.py` verify schemas `kube-actuary.version-worklist.v1`, `kube-actuary.version-iteration.v1`, `kube-actuary.version-iteration-diff.v1`, `kube-actuary.version-iteration-history.v1`, `kube-actuary.version-iteration-history-status.v1`, and `kube-actuary.next-version-task.v1` for version-grouped open work, text/Markdown local task output, prepared queue reuse, blocker summaries, blocker-focused filters including environment reasons, evidence-dir file readiness, evidence-aware local iteration packs, pack diffs, queue-source-preserving run history, history inspection with latest next-task worklist drilldowns and latest advance/runner status, next-task selection, deterministic evidence-directory command paths, and `--skip-complete-evidence` completed-evidence skipping |
| External gate plan | DONE | `scripts/verify_external_gate_plan.py` verifies remaining VERIFY rows and evidence commands |
| External gate command safety | DONE | `scripts/verify_external_gate_command_safety.py` verifies generated external commands stay dry-run/read-only/evidence-only |
| External gate evidence evaluation | DONE | `scripts/verify_external_gate_evidence.py` maps captured smoke manifests to VERIFY rows |
| External evidence builder | DONE | `scripts/verify_external_evidence_builder.py` verifies supplemental evidence record generation |
| External evidence bundle | DONE | `scripts/verify_external_evidence_bundle.py` verifies auditable evidence bundle generation |
| Release evidence directory | DONE | `scripts/verify_release_evidence_directory.py` verifies repeated evidence directory artifact generation |
| Release evidence status | DONE | `scripts/verify_release_evidence_status.py` verifies partial evidence directory status inspection plus version-scoped `--version` coverage totals, missing gates, blocker drilldowns, persisted next-task output, file readiness, evidence-build status, queue-source visibility/origin, next-task queue consistency, runner/build/advance record consistency, and legacy prepared-record source inference |
| Next task evidence builder | DONE | `scripts/build_next_task_evidence.py` and `scripts/verify_release_evidence_status.py` build and record selected local supplemental evidence from captured raw files |
| Next version task runner | DONE | `scripts/run_next_version_task.py` and `scripts/verify_next_version_task_runner.py` plan, run, record selected safe evidence commands, preserve queue source, and keep non-`tool-ready` tasks at zero-run status from a prepared evidence directory |
| Version iteration advance | DONE | `scripts/advance_version_iteration.py` and `scripts/verify_version_iteration_advance.py` verify schema `kube-actuary.version-iteration-advance.v1` for one selected task plus version-scoped `--version`, blocker-focused filters such as `--missing-tool`, selected worklist drilldowns, probe-aware before/after history, queue-source-preserving `.kubeactuary/next-version-task-run.json`, and `.kubeactuary/version-iteration-advance.json` status recording |
| Clean artifact hygiene | DONE | `scripts/verify_clean_artifacts.py` verifies no generated Python cache artifacts remain |
| Structured help contract | DONE | schema version and compatibility tests |
| Human and agent help | DONE | `kube-actuary help`, `kube-actuary help agents --format json` |
| CRD seed | DONE | YAML parse, CRD field contract tests, and `render-crd` status mapping tests |
| CRD compatibility smoke | DONE | offline upstream N/N-1/N-2 and managed-source checks |
| CRD upgrade fixtures | DONE | rollback fixture, runbook, and offline fixture verifier |
| CRD explain quality | DONE | OpenAPI descriptions, explain runbook, and offline verifier |
| Controller reconcile model | DONE | pure status reconcile tests and dry-run controller contract |
| Controller RBAC | DONE | namespace and cluster mode manifests plus offline RBAC verifier |
| Controller runtime contract | DONE | health, readiness, metrics, and Lease config verifier |
| Controller deployment seed | DONE | `scripts/verify_controller_deployment.py` verifies optional Deployment runtime defaults |
| Controller status patch plan | DONE | `scripts/verify_controller_patch_plan.py` verifies status-only patch plans without executing writes |
| Controller read-only sync | DONE | `scripts/verify_controller_sync.py` verifies `kubectl get` plus disabled write execution |
| Controller status apply dry-run | DONE | `scripts/verify_controller_status_apply.py` verifies default server dry-run and explicit status-only execute shape |
| Controller status loop dry-run | DONE | `scripts/verify_controller_loop.py` verifies repeated read/status-patch ticks stay server-side dry-run by default |
| Controller resource budget | VERIFY | offline budget verifier and read-only capture helper added; live kind/minikube/k3s measurements still needed |
| Lightweight cluster smoke | VERIFY | offline smoke plan and JSON evidence-output verifier added; live matrix evidence still needed |
| Helm chart | VERIFY | chart seed, dry-run smoke harness, and offline verifier added; live Helm run not executed because Helm is not installed |
| Kustomize | DONE | base and controller overlays render with `kubectl kustomize` |
| Release archives | DONE | multi-target archive generator, SHA-256 sidecars, and install smoke verifier |
| Krew manifest | VERIFY | manifest generator, isolated smoke harness, and offline verifier added; real Krew install validation not run because Krew is not installed |
| SBOM and provenance | DONE | deterministic SBOM/provenance generators and archive digest verifier |
| Air-gapped install | DONE | offline artifact manifest generator and verifier |
| Kyverno adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| OPA adapter | DONE | captured OPA eval JSON adapter with pass/fail fixture verifier |
| kube-linter adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| kube-score adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| Pluto adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| Adapter contract | DONE | common fields and normalized severity verifier |
| Live validation readiness | DONE | `scripts/verify_live_validation_readiness.py` inventories external gates and missing tools without running them; optional environment probe classifies current cluster availability and stable failure reasons without writes |
| Live validation queue | DONE | `scripts/generate_live_validation_queue.py` and `scripts/verify_live_validation_queue.py` verify schema `kube-actuary.live-validation-queue.v1` for ordered evidence commands plus environment-blocked gates and probe reasons |
| Live validation queue safety | DONE | `scripts/verify_live_validation_queue_safety.py` verifies placeholder and resolved queue commands stay dry-run/read-only/evidence-only |
| Live evidence directory scaffold | DONE | `scripts/prepare_live_evidence_directory.py` and `scripts/verify_live_evidence_directory_scaffold.py` verify local reports/raw/supplemental/.kubeactuary scaffold generation plus prepared-queue-sourced, version-scoped `--version`, blocker-filtered `--missing-tool`/`--environment-reason`, and probe-aware next-task artifacts, schemas `kube-actuary.environment-probe.v1` and `kube-actuary.environment-blockers.v1`, and `--skip-complete-evidence` advancement |
| Live evidence schema | DONE | `scripts/verify_live_evidence_schema.py` validates supported captured evidence report schemas |
| Live evidence manifest | DONE | `scripts/verify_live_evidence_manifest.py` verifies captured report manifest generation |
| Live evidence coverage | DONE | `scripts/verify_live_evidence_coverage.py` verifies release-gate and provider coverage rules |
| Managed Kubernetes smoke | VERIFY | `scripts/verify_managed_kubernetes_smoke.py` verifies EKS/GKE/AKS plan and evidence JSON; provider runs still needed |
| Project governance | DONE | `scripts/verify_project_governance.py` verifies LICENSE, NOTICE, SECURITY, and CONTRIBUTING |
| Controller | VERIFY | Optional `serve` runtime, Deployment seed, status patch plan, read-only sync, status apply dry-run, and status loop exist; live cluster loop/resource evidence remains |
| Packaging | VERIFY | Helm/Krew live validation remains; local chart, Kustomize, archive, SBOM, provenance, and air-gapped verifiers exist |
| MCP server | DONE | safe stdlib JSON-RPC wrapper, client config, docs, and contract verifier exist |
| Admission/audit | VERIFY | offline webhook manifest, policy evaluator, local server, response builder, audit fixtures, and kind smoke evidence harness exist; live kind webhook smoke remains |

Last local verification:

```text
2026-07-06: python3 -B scripts/verify_release.py --version 0.2.0
verification: passed (79 checks)
```

## v0.2.x: Alpha Stabilization

Goal: make the local CLI and evidence collector workflow release-quality before
adding in-cluster components.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.2.0 | Evidence collectors: auth, dry-run, diff, rollback, health-plan | DONE | `scripts/verify_release.py --version 0.2.0` |
| 0.2.0 | Human help and agent JSON help | DONE | `kube-actuary help agents --format json` parses |
| 0.2.0 | Local release verification suite | DONE | `scripts/verify_release.py --list` and v0.2.0 pass |
| 0.2.1 | Add `validate` command for capsule JSON/schema checks | DONE | valid/invalid/json-output tests plus release suite check |
| 0.2.1 | Add `doctor` command for local dependencies and kubectl skew hints | DONE | fake kubectl path/version/skew tests plus release suite check |
| 0.2.1 | Normalize collector error summaries and inapplicable evidence | DONE | unit tests for missing manifest/path/command failure summaries |
| 0.2.2 | Add GitHub Actions CI for tests, JSON/YAML parse, release verification | DONE | workflow YAML parse plus `scripts/verify_release.py --version current` in CI |
| 0.2.2 | Add release checklist and generated release notes template | DONE | `scripts/generate_release_notes.py --version 0.2.0 --output -` |
| 0.2.3 | Add release taskboard audit | DONE | `scripts/verify_release_taskboard.py` checks status rows and release check count |
| 0.2.3 | Add structured help schema version and compatibility test | DONE | `help agents --format json` schemaVersion and required field tests |
| 0.2.3 | Add clean generated-artifact verification | DONE | `scripts/verify_clean_artifacts.py` checks Python cache directories and bytecode files |

## v0.3.x: CRD API Contract

Goal: make `OperationCapsule.ops.kubeactuary.dev/v1alpha1` a usable Kubernetes
API surface across upstream-supported Kubernetes versions and managed services.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.3.0 | Freeze CRD field names for `spec`, embedded evidence, rollback, and status | DONE | CRD schema field contract tests |
| 0.3.0 | Add status condition mapping: `EvidenceComplete`, `GateOpen`, `Blocked`, `RollbackReady`, `Expired` | DONE | rendered CRD status condition tests |
| 0.3.1 | Add CRD validation smoke for Kubernetes upstream N/N-1/N-2 | VERIFY | offline `scripts/verify_crd_compatibility.py`; live kind/minikube matrix not run locally |
| 0.3.1 | Add managed-service notes for EKS, GKE, AKS support windows | DONE | `docs/kubernetes-compatibility.md` source snapshot and smoke check |
| 0.3.2 | Add CRD upgrade/rollback fixtures | DONE | offline rollback fixture verifier; live disposable-cluster apply still recommended before public CRD release |
| 0.3.3 | Add `kubectl explain` quality checks and examples | VERIFY | offline explain-quality verifier and runbook; live `kubectl explain` smoke not run locally |

## v0.4.x: Low-Overhead Controller

Goal: add an optional controller that only watches KubeActuary resources and
patches status. It must not scan the cluster or execute writes.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.4.0 | Implement read-only controller reconciliation model | DONE | pure fake-client tests and `bin/kube-actuary-controller reconcile` |
| 0.4.0 | Watch only `OperationCapsule` resources | DONE | `watch-command` contract and verifier |
| 0.4.1 | Minimal RBAC, namespace-scoped and cluster-scoped modes | DONE | `scripts/verify_controller_rbac.py`; live cluster smoke remains v0.4.4 |
| 0.4.2 | Health, readiness, metrics, leader election | DONE | `scripts/verify_controller_runtime_contract.py`; live pod lifecycle smoke remains v0.4.4 |
| 0.4.2 | Optional controller Deployment seed | DONE | `scripts/verify_controller_deployment.py`; live image/pod smoke remains v0.4.4 |
| 0.4.2 | Status patch plan for watched capsules | DONE | `scripts/verify_controller_patch_plan.py`; live patch execution remains v0.4.4 |
| 0.4.2 | Read-only sync from watched capsules | DONE | `scripts/verify_controller_sync.py`; live status apply loop remains v0.4.4 |
| 0.4.3 | Status apply dry-run for watched capsules | DONE | `scripts/verify_controller_status_apply.py`; persistent live loop remains v0.4.4 |
| 0.4.3 | Status loop dry-run for watched capsules | DONE | `scripts/verify_controller_loop.py`; live cluster loop evidence remains v0.4.4 |
| 0.4.3 | Resource budget target: idle <50m CPU and <64Mi memory | VERIFY | `scripts/verify_controller_resource_budget.py`; live kind/minikube/k3s measurement still required |
| 0.4.4 | Lightweight-cluster smoke: kind, minikube, MicroK8s, k3s | VERIFY | `scripts/verify_lightweight_cluster_smoke.py` verifies plan and evidence JSON; live matrix evidence still required |

## v0.5.x: Packaging and Installation

Goal: make KubeActuary installable as a serious Kubernetes open-source tool.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.5.0 | Helm chart for CRD and optional controller | VERIFY | `scripts/verify_helm_chart.py` and `scripts/run_helm_smoke.py`; live Helm run still required |
| 0.5.0 | Kustomize base and overlays | DONE | `scripts/verify_kustomize.py` runs `kubectl kustomize` for base and overlays |
| 0.5.1 | Multi-arch release archives for CLI/plugin | DONE | `scripts/verify_release_archives.py` generates archives, verifies SHA-256, and runs install smoke |
| 0.5.2 | Krew manifest for `kubectl actuary` | VERIFY | `scripts/verify_krew_manifest.py` and `scripts/run_krew_smoke.py`; real Krew run still required |
| 0.5.3 | SBOM and provenance generation | DONE | `scripts/verify_supply_chain.py` validates SBOM and archive provenance |
| 0.5.4 | Air-gapped install documentation | DONE | `scripts/verify_airgap_bundle.py` validates offline artifact checklist |

## v0.6.x: Policy and Evidence Adapters

Goal: connect existing policy/readiness tools as evidence producers without
replacing them.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.6.0 | Kyverno CLI evidence adapter | DONE | `scripts/verify_kyverno_adapter.py` validates pass/fail fixtures |
| 0.6.0 | OPA/Rego evidence adapter | DONE | `scripts/verify_opa_adapter.py` validates pass/fail fixtures |
| 0.6.1 | kube-linter and kube-score evidence adapters | DONE | `scripts/verify_kube_linter_adapter.py` and `scripts/verify_kube_score_adapter.py` validate pass/fail fixtures |
| 0.6.2 | Pluto deprecated API evidence adapter | DONE | `scripts/verify_pluto_adapter.py` validates pass/fail fixtures |
| 0.6.3 | Adapter result schema and severity normalization | DONE | `scripts/verify_adapter_contract.py` validates common fields and severity |

## v0.7.x: Agent and MCP Integration

Goal: let AI tools use KubeActuary safely without exposing raw cluster write
execution by default.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.7.0 | Safe MCP tools: draft, inspect, attach, verify, gate | DONE | `scripts/verify_mcp_contract.py` validates JSON-RPC/MCP contract |
| 0.7.1 | Agent help contract versioning | DONE | `scripts/verify_agent_help_contract.py` validates schema compatibility |
| 0.7.2 | Agent examples for local CI and Codex workflows | DONE | `scripts/verify_agent_examples.py` validates local CI and Codex runbooks |
| 0.7.3 | Explicitly disabled experimental execute tool | DONE | `scripts/verify_execute_disabled.py` proves CLI/MCP execute is absent or disabled |
| 0.7.4 | MCP client config and docs | DONE | `scripts/verify_mcp_docs.py` validates safe client config and guide |

## v0.8.x: Optional Admission and Audit

Goal: offer admission enforcement only for clusters that accept webhook
operational risk. This remains optional.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.8.0 | Validating admission webhook prototype | VERIFY | `scripts/verify_admission_webhook.py` and `scripts/run_admission_kind_smoke.py`; live kind smoke pending because kind is not installed |
| 0.8.1 | AI identity selector and annotation requirements | DONE | `scripts/verify_admission_policy.py` validates allow/deny fixtures |
| 0.8.2 | Capsule digest and gate verification | DONE | `scripts/verify_admission_digest_gate.py` validates digest and closed-gate tamper fixtures |
| 0.8.3 | Audit annotations and incident runbook | DONE | `scripts/verify_admission_audit.py` validates audit fixtures and incident runbook |
| 0.8.4 | AdmissionReview response builder | DONE | `scripts/verify_admission_response.py` validates response and audit annotations |
| 0.8.5 | Local admission HTTP server | DONE | `scripts/verify_admission_server.py` validates `/validate` without cluster access |

## v0.9.x: Release Candidate

Goal: freeze public contracts and prove compatibility before v1.0.0.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.9.0 | Conformance suite for upstream supported Kubernetes minors | DONE | `scripts/verify_conformance_suite.py` validates N/N-1/N-2 matrix |
| 0.9.0 | Managed Kubernetes smoke: EKS, GKE, AKS | VERIFY | `scripts/verify_managed_kubernetes_smoke.py`; provider run evidence still required |
| 0.9.1 | Security policy, threat model, disclosure process | DONE | `scripts/verify_security_docs.py` validates `SECURITY.md` and threat model |
| 0.9.2 | API freeze and upgrade compatibility gate | DONE | `scripts/verify_api_freeze.py` guards additive-only no breaking schema diff |
| 0.9.3 | Documentation freeze and public examples audit | DONE | `scripts/verify_docs_freeze.py` checks public docs and examples |
| 0.9.4 | Live validation readiness ledger | DONE | `scripts/verify_live_validation_readiness.py` tracks remaining external evidence gates and missing tools |
| 0.9.4 | Captured live evidence schema validator | DONE | `scripts/verify_live_evidence_schema.py` validates five smoke evidence schemas |
| 0.9.4 | Captured live evidence manifest | DONE | `scripts/verify_live_evidence_manifest.py` maps smoke reports to release gates |
| 0.9.4 | Captured live evidence coverage | DONE | `scripts/verify_live_evidence_coverage.py` requires provider and gate coverage |
| 0.9.5 | Project governance and contribution policy | DONE | `scripts/verify_project_governance.py` checks contribution, notice, security, and license files |

## v1.0.0: GA

Goal: a stable, low-overhead evidence contract for AI-assisted Kubernetes
operations.

Release gates:

- CLI, CRD, controller, packaging, MCP-safe tools, and docs are all verified.
- Default behavior still does not execute proposed Kubernetes writes.
- Controller watches only KubeActuary CRDs.
- Admission remains optional.
- Support matrix is documented for upstream-supported Kubernetes minors,
  EKS/GKE/AKS GA versions, and best-effort lightweight distributions.
- License, NOTICE, SECURITY, CONTRIBUTING, and release provenance are complete.

## Compatibility Policy

- Official support follows upstream Kubernetes supported minors at release time.
- Managed service support follows GA versions for EKS, GKE, and AKS.
- Best-effort validation covers kind, minikube, MicroK8s, and k3s.
- Unsupported/EOL Kubernetes versions should warn, not hard fail, unless a
  required Kubernetes API is missing.
- `kubectl` compatibility follows the upstream `kubectl` skew policy.

## License Track

Current license: MIT.

Decision needed before v0.3.0:

- Keep MIT for maximum simplicity, or
- move to Apache-2.0 before external contributions grow, adding explicit patent
  grant, `NOTICE`, `THIRD_PARTY_NOTICES`, SPDX headers, DCO, and contribution
  policy.

Recommended default for v1.0.0: Apache-2.0, because KubeActuary is becoming a
Kubernetes ecosystem infrastructure project with controller/admission/MCP
surfaces.
