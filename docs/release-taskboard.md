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
| Structured help contract | DONE | schema version and compatibility tests |
| Human and agent help | DONE | `kube-actuary help`, `kube-actuary help agents --format json` |
| CRD seed | DONE | YAML parse, CRD field contract tests, and `render-crd` status mapping tests |
| CRD compatibility smoke | DONE | offline upstream N/N-1/N-2 and managed-source checks |
| CRD upgrade fixtures | DONE | rollback fixture, runbook, and offline fixture verifier |
| CRD explain quality | DONE | OpenAPI descriptions, explain runbook, and offline verifier |
| Controller reconcile model | DONE | pure status reconcile tests and dry-run controller contract |
| Controller RBAC | DONE | namespace and cluster mode manifests plus offline RBAC verifier |
| Controller runtime contract | DONE | health, readiness, metrics, and Lease config verifier |
| Controller resource budget | VERIFY | offline budget verifier added; live kind/minikube/k3s measurements still needed |
| Lightweight cluster smoke | VERIFY | offline smoke plan verifier added; live matrix evidence still needed |
| Helm chart | VERIFY | chart seed and offline verifier added; live `helm template` not run because Helm is not installed |
| Kustomize | DONE | base and controller overlays render with `kubectl kustomize` |
| Release archives | DONE | multi-target archive generator, SHA-256 sidecars, and install smoke verifier |
| Krew manifest | VERIFY | manifest generator and offline verifier added; real Krew install validation not run because Krew is not installed |
| SBOM and provenance | DONE | deterministic SBOM/provenance generators and archive digest verifier |
| Air-gapped install | DONE | offline artifact manifest generator and verifier |
| Kyverno adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| OPA adapter | DONE | captured OPA eval JSON adapter with pass/fail fixture verifier |
| kube-linter adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| kube-score adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| Pluto adapter | DONE | captured JSON adapter with pass/fail fixture verifier |
| Adapter contract | DONE | common fields and normalized severity verifier |
| Controller | TODO | No live controller deployment yet |
| Packaging | DOING | Helm/Krew live validation remains; local chart, Kustomize, archive, SBOM, provenance, and air-gapped verifiers exist |
| MCP server | DOING | safe stdlib JSON-RPC wrapper exists; examples/versioning remain |
| Admission/audit | TODO | Contract docs only |

Last local verification:

```text
2026-07-06: python3 -B scripts/verify_release.py --version 0.2.0
verification: passed (42 checks)
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
| 0.2.3 | Add structured help schema version and compatibility test | DONE | `help agents --format json` schemaVersion and required field tests |

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
| 0.4.3 | Resource budget target: idle <50m CPU and <64Mi memory | VERIFY | `scripts/verify_controller_resource_budget.py`; live kind/minikube/k3s measurement still required |
| 0.4.4 | Lightweight-cluster smoke: kind, minikube, MicroK8s, k3s | VERIFY | `scripts/verify_lightweight_cluster_smoke.py`; live matrix evidence still required |

## v0.5.x: Packaging and Installation

Goal: make KubeActuary installable as a serious Kubernetes open-source tool.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.5.0 | Helm chart for CRD and optional controller | VERIFY | `scripts/verify_helm_chart.py`; live `helm template` and install smoke still required |
| 0.5.0 | Kustomize base and overlays | DONE | `scripts/verify_kustomize.py` runs `kubectl kustomize` for base and overlays |
| 0.5.1 | Multi-arch release archives for CLI/plugin | DONE | `scripts/verify_release_archives.py` generates archives, verifies SHA-256, and runs install smoke |
| 0.5.2 | Krew manifest for `kubectl actuary` | VERIFY | `scripts/verify_krew_manifest.py`; real Krew install validation still required |
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

## v0.8.x: Optional Admission and Audit

Goal: offer admission enforcement only for clusters that accept webhook
operational risk. This remains optional.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.8.0 | Validating admission webhook prototype | VERIFY | `scripts/verify_admission_webhook.py` validates `failurePolicy: Ignore`; live kind smoke pending because kind is not installed |
| 0.8.1 | AI identity selector and annotation requirements | DONE | `scripts/verify_admission_policy.py` validates allow/deny fixtures |
| 0.8.2 | Capsule digest and gate verification | TODO | tamper fixtures |
| 0.8.3 | Audit annotations and incident runbook | TODO | audit fixture review |

## v0.9.x: Release Candidate

Goal: freeze public contracts and prove compatibility before v1.0.0.

| Version | Task | Status | Verification |
| --- | --- | --- | --- |
| 0.9.0 | Conformance suite for upstream supported Kubernetes minors | TODO | N/N-1/N-2 matrix |
| 0.9.0 | Managed Kubernetes smoke: EKS, GKE, AKS | TODO | provider run evidence |
| 0.9.1 | Security policy, threat model, disclosure process | TODO | `SECURITY.md` review |
| 0.9.2 | API freeze and upgrade compatibility gate | TODO | no breaking schema diff |
| 0.9.3 | Documentation freeze and public examples audit | TODO | docs checklist |

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
