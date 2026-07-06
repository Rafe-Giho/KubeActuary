# KubeActuary

<p align="center">
  <img src="assets/brand/kubeactuary-symbol.png" alt="KubeActuary symbol" width="180">
</p>

> Evidence-carrying operations for AI-assisted Kubernetes.

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.x-3776AB)](bin/kube-actuary)
[![Kubernetes](https://img.shields.io/badge/kubernetes-CRD%20seed-326CE5)](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)

English | [한국어](README.ko.md)

KubeActuary is a model-free CLI and Kubernetes-native specification for making
AI-originated Kubernetes operations carry evidence before they can be considered
for execution.

It is not another Kubernetes chatbot. It is the execution boundary beneath one.

```text
AI / human intent
  -> OperationCapsule
  -> evidence collection
  -> gate decision
  -> human, CI, GitOps, or future bounded execution
```

## The Problem

Modern AI tools can already talk to Kubernetes:

- `kubectl-ai` can translate natural language into Kubernetes actions.
- `k8sgpt` can analyze cluster symptoms.
- MCP servers can expose cluster tools to agents.
- Kyverno, OPA, kube-linter, kube-score, Polaris, and Trivy can evaluate policy,
  readiness, and security.
- GitOps can reconcile desired state.

What is still missing is a small shared contract for this question:

> Before an AI-originated Kubernetes action changes anything, what evidence must
> it carry?

KubeActuary answers that with an `OperationCapsule`.

## The Primitive: OperationCapsule

An `OperationCapsule` is a portable operation record:

| Field | Purpose |
| --- | --- |
| Intent | Why the operation exists |
| Proposed action | Command or manifest path |
| Target | Resource, namespace, scope, and verb |
| Risk | Basic blast-radius estimate |
| Required evidence | Auth, dry-run, diff, rollback, approval, post-checks |
| Status evidence | Attached proof records |
| Gate | Open only when required evidence passes |

The capsule can be created by an AI, reviewed by a human, checked in to Git,
verified in CI, rendered as a CRD object, or consumed by a future controller.

## What Works in v0.2.0

- Draft local operation capsules from `kubectl` commands or manifest paths.
- Inspect target, risk, state, and evidence.
- Validate capsule JSON structure without contacting the cluster.
- Check local runtime and `kubectl` client diagnostics.
- Attach manual evidence.
- Collect `kubectl auth can-i` evidence.
- Collect server-side dry-run evidence for manifest-based operations.
- Collect `kubectl diff` evidence for manifest-based operations.
- Attach explicit rollback command or manifest evidence.
- Attach declared post-change health-plan evidence.
- Print a deterministic spec digest for audit references.
- Verify missing or failed evidence.
- Open or close an execution gate.
- Render a local capsule as a Kubernetes `OperationCapsule` CRD object.
- Render CRD status fields and condition mappings for local capsule state.
- Use the CLI as a `kubectl` plugin.
- Validate against a JSON Schema and CRD seed.

Non-goals for v0.2.0:

- no direct cluster write execution;
- no in-cluster LLM;
- no controller requirement;
- no admission webhook;
- no external Python package dependency.

## Quick Start

Create a high-risk draft:

```sh
python3 bin/kube-actuary draft \
  --intent "increase checkout API capacity for expected traffic" \
  --command "kubectl scale deployment checkout-api --replicas=6 -n prod" \
  --actor "ai-agent" \
  --out /tmp/scale.capsule.json
```

Inspect it:

```sh
python3 bin/kube-actuary inspect /tmp/scale.capsule.json
```

Validate the capsule structure:

```sh
python3 bin/kube-actuary validate /tmp/scale.capsule.json
```

`validate` checks the local capsule contract. Evidence completeness is checked
by `verify` and `gate`.

Check local prerequisites:

```sh
python3 bin/kube-actuary doctor
```

The gate is closed because this is only a proposal:

```sh
python3 bin/kube-actuary gate /tmp/scale.capsule.json
```

Attach approval evidence:

```sh
python3 bin/kube-actuary attach-evidence /tmp/scale.capsule.json \
  --id owner-approval \
  --summary "checkout service owner approved the scale-up window" \
  --actor "platform-reviewer" \
  --out /tmp/scale.with-approval.json
```

Collect live authorization evidence without running the proposed write:

```sh
python3 bin/kube-actuary collect auth /tmp/scale.with-approval.json \
  --out /tmp/scale.with-auth.json
```

For manifest-based changes, collect preflight evidence without persisting a
cluster write:

```sh
python3 bin/kube-actuary collect dry-run /tmp/apply.capsule.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-dry-run.json

python3 bin/kube-actuary collect diff /tmp/apply.with-dry-run.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-diff.json
```

Attach rollback and post-change health-plan evidence:

```sh
python3 bin/kube-actuary collect rollback /tmp/apply.with-diff.json \
  --manifest examples/configmap-demo.rollback.yaml \
  --out /tmp/apply.with-rollback.json

python3 bin/kube-actuary collect health-plan /tmp/apply.with-rollback.json \
  --out /tmp/apply.with-health.json
```

Render a local capsule as a Kubernetes resource:

```sh
python3 bin/kube-actuary render-crd examples/read-pods.verified.capsule.json \
  --name read-pods \
  --namespace default
```

Verify the included read-only example:

```sh
python3 bin/kube-actuary verify examples/read-pods.verified.capsule.json
python3 bin/kube-actuary gate examples/read-pods.verified.capsule.json
```

Expected:

```text
gate: open
id: opcap-example-read-pods
risk: low
command: kubectl get pods -n default
```

## CLI

```text
draft              Create an OperationCapsule draft
inspect            Summarize target, risk, state, and evidence
validate           Validate capsule JSON structure
doctor             Check local runtime and kubectl diagnostics
attach-evidence    Attach manual evidence
collect auth       Collect kubectl auth can-i evidence
collect dry-run    Collect server-side dry-run evidence
collect diff       Collect kubectl diff evidence
collect rollback   Attach rollback command or manifest evidence
collect health-plan Attach declared post-change checks
digest             Print deterministic capsule spec digest
help               Show workflow, safety, evidence, or agent guidance
verify             Check required evidence
gate               Print open/closed execution decision
render-crd         Render a capsule as a Kubernetes CRD object
demo               Print a sample high-risk capsule
```

Version:

```sh
python3 bin/kube-actuary --version
```

Human-readable help:

```sh
python3 bin/kube-actuary help
python3 bin/kube-actuary help workflow
python3 bin/kube-actuary help safety
```

Agent-readable help:

```sh
python3 bin/kube-actuary help agents --format json
```

The JSON help describes command safety, cluster access, evidence ids, stable
exit-code meanings, operations the CLI never executes, and a versioned
`schemaVersion`/`compatibility` contract for agent integrations.

## Kubectl Plugin

Kubernetes discovers plugins as executables named `kubectl-*` on `PATH`.
This repository includes `bin/kubectl-actuary`.

```sh
export PATH="$PWD/bin:$PATH"
kubectl actuary draft \
  --intent "inspect pods" \
  --command "kubectl get pods -n default"
```

## Kubernetes-Native Path

KubeActuary includes a lightweight CRD seed:

- [deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)
- [examples/operationcapsule-scale.yaml](examples/operationcapsule-scale.yaml)

Design constraints:

- one namespaced `OperationCapsule` resource;
- embedded evidence first, no separate `Evidence` CRD yet;
- controller should watch only KubeActuary resources;
- no cluster-wide scans;
- no in-cluster LLM;
- no write execution in the first controller version.

## Safety Model

KubeActuary separates proposal, evidence, approval, and execution.

| Responsibility | Typical actor |
| --- | --- |
| Proposal | AI agent, human, CI |
| Evidence collection | CLI, CI, policy tools |
| Approval | human/platform owner |
| Execution | human, GitOps, future bounded executor |

A high-risk AI proposal can exist without being allowed to mutate the cluster.
That separation is the product.

## Repository Layout

```text
bin/
  kube-actuary                 CLI
  kube-actuary-controller      dry-run controller reconcile helper
  kubectl-actuary              kubectl plugin entrypoint
CONTRIBUTING.md                contribution and safety boundary guide
controller/
  reconcile.py                 pure OperationCapsule status reconcile model
.github/workflows/
  ci.yml                       GitHub Actions verification workflow
SECURITY.md                    security policy and disclosure process
NOTICE                         project notice and attribution status
charts/
  kubeactuary/                 Helm chart seed
deploy/crds/
  operationcapsules...yaml     CRD seed
  fixtures/                    CRD upgrade and rollback fixtures
deploy/controller/
  *-rbac.yaml                  optional controller RBAC manifests
  deployment.yaml              optional controller runtime Deployment seed
deploy/admission/
  validatingwebhookconfiguration.yaml optional admission webhook prototype
deploy/kustomize/
  base/                        CRD-only Kustomize base
  overlays/                    optional controller RBAC overlays
docs/
  admission.md                optional admission prototype and safety defaults
  admission-kind-smoke.md     optional kind admission smoke runbook
  admission-incident-runbook.md admission audit incident runbook
  api-freeze.md               additive API freeze and compatibility gate
  conformance.md              upstream N/N-1/N-2 conformance suite
  docs-freeze.md              release-candidate public docs checklist
  threat-model.md             project threat model
  collectors.md                evidence collector contract
  landscape.md                 ecosystem research
  paradigm.md                  operating model
  project-assessment.md        maturity assessment
  release-checklist.md         release gate checklist
  release-taskboard.md         local v1.0 taskboard
  release-archives.md          release archive build and verification
  supply-chain.md              SBOM and provenance generation
  air-gapped-install.md        offline install artifact checklist
  krew.md                      Krew manifest generation and verification
  helm-smoke.md                Helm template and dry-run install smoke runbook
  live-validation.md           external live validation evidence ledger
  managed-kubernetes-smoke.md  EKS/GKE/AKS smoke runbook
  mcp.md                       MCP client config and safe-tool guide
  policy-adapters.md           policy evidence adapter contracts
  kustomize.md                 Kustomize install and verification runbook
  lightweight-cluster-smoke.md kind/minikube/MicroK8s/k3s smoke runbook
  kubernetes-compatibility.md  Kubernetes and managed-service compatibility
  crd-upgrade-rollback.md      CRD fixture upgrade and rollback runbook
  controller.md                low-overhead controller design and contract
  kubectl-explain.md           kubectl explain quality runbook
  roadmap.md                   development plan
  v0.1.0.md                    alpha release goal
  test-plan-v0.2.0.md          v0.2.0 release test plan
  test-results-v0.2.0.md       latest verification result
  test-plan-v0.1.0.md          release test plan
  test-results-v0.1.0.md       v0.1.0 verification result
  crd-design.md                Kubernetes-native design
  interoperability.md          CLI, MCP, GitOps, admission contracts
  novelty-check.md             novelty boundary
examples/
  *.capsule.json               local capsule examples
  operationcapsule-scale.yaml  CRD example
  mcp-client-config.json       safe MCP client config example
  agent-local-ci.runbook.md    local CI agent workflow runbook
  agent-codex-workflow.runbook.md Codex agent workflow runbook
schemas/
  operation-capsule...json     JSON Schema
  api-freeze.v0.9.2.json       frozen public API compatibility contract
scripts/
  generate_release_notes.py    release notes dry-run generator
  verify_release_taskboard.py  local release taskboard audit
  generate_release_progress.py versioned release progress report generator
  verify_release_progress.py   release progress verifier
  kube-actuary.release-progress.v1 release progress schema
  generate_version_worklist.py version-grouped task worklist generator with filters and evidence readiness
  prepare_version_iteration.py local version iteration pack generator with evidence readiness
  compare_version_iterations.py local version iteration diff generator
  record_version_iteration.py local version iteration history recorder with evidence readiness
  inspect_version_history.py local version iteration history inspector with evidence status
  select_next_version_task.py local next version task selector with evidence skip support
  verify_version_worklist.py version worklist verifier
  kube-actuary.version-worklist.v1 version worklist schema
  kube-actuary.version-iteration.v1 version iteration schema
  kube-actuary.version-iteration-diff.v1 version iteration diff schema
  kube-actuary.version-iteration-history.v1 version iteration history schema
  kube-actuary.version-iteration-history-status.v1 version iteration history status schema
  kube-actuary.next-version-task.v1 next version task schema
  generate_external_gate_plan.py external verification gate plan generator
  verify_external_gate_plan.py external verification gate plan verifier
  verify_external_gate_command_safety.py external gate command safety verifier
  evaluate_external_gate_evidence.py external gate evidence evaluator
  verify_external_gate_evidence.py external gate evidence verifier
  build_external_evidence.py supplemental external evidence builder
  verify_external_evidence_builder.py supplemental evidence builder verifier
  kube-actuary.external-evidence.v1 supplemental evidence schema
  build_external_evidence_bundle.py external evidence bundle builder
  verify_external_evidence_bundle.py external evidence bundle verifier
  kube-actuary.external-evidence-bundle.v1 external evidence bundle schema
  build_release_evidence_directory.py release evidence directory builder
  verify_release_evidence_directory.py release evidence directory verifier
  inspect_release_evidence_directory.py release evidence, next-task, runner, environment, and advance status inspector/recorder
  build_next_task_evidence.py local next-task supplemental evidence builder
  verify_release_evidence_status.py release evidence status verifier
  kube-actuary.release-evidence-status.v1 release evidence status schema
  release-evidence-status.json persisted release evidence status report
  kube-actuary.next-task-evidence-build.v1 next task evidence build schema
  verify_clean_artifacts.py generated Python cache artifact verifier
  verify_crd_compatibility.py  offline CRD compatibility smoke check
  verify_crd_explain_quality.py offline kubectl explain quality check
  verify_crd_upgrade_fixtures.py offline CRD upgrade fixture check
  verify_controller_contract.py offline controller contract check
  verify_controller_rbac.py    offline controller RBAC check
  verify_controller_runtime_contract.py offline controller runtime check
  verify_controller_deployment.py optional controller Deployment seed check
  verify_controller_patch_plan.py status patch plan verifier
  verify_controller_sync.py       read-only controller sync verifier
  verify_controller_status_apply.py status patch dry-run verifier
  verify_controller_loop.py   controller loop dry-run verifier
  verify_controller_resource_budget.py offline controller resource budget check
  measure_controller_resources.py kubectl top budget measurement helper with text/JSON output
  capture_controller_resource_budget.py read-only kubectl top evidence capture helper (`controller-resource-capture`)
  verify_controller_resource_capture.py controller resource evidence capture verifier
  run_lightweight_cluster_smoke.py lightweight cluster smoke harness with JSON evidence output
  verify_lightweight_cluster_smoke.py offline smoke harness check
  verify_conformance_suite.py upstream N/N-1/N-2 conformance verifier
  run_managed_kubernetes_smoke.py EKS/GKE/AKS smoke harness
  verify_managed_kubernetes_smoke.py offline managed smoke verifier
  run_helm_smoke.py           Helm template and dry-run install smoke harness
  verify_helm_chart.py        offline Helm chart contract check
  verify_kustomize.py         Kustomize render check
  package_release_archives.py release archive generator
  verify_release_archives.py  archive checksum and install smoke
  generate_krew_manifest.py   Krew manifest generator
  run_krew_smoke.py           Krew install smoke harness with isolated KREW_ROOT
  verify_krew_manifest.py     offline Krew manifest check
  generate_sbom.py            CycloneDX SBOM generator
  generate_provenance.py      release archive provenance generator
  verify_supply_chain.py      SBOM/provenance verifier
  verify_security_docs.py     security policy and threat model verifier
  verify_api_freeze.py        additive API freeze verifier
  verify_docs_freeze.py       public docs and examples verifier
  verify_live_validation_readiness.py external validation readiness inventory and optional environment probe
  generate_live_validation_queue.py live validation queue generator with optional environment probe
  verify_live_validation_queue.py live validation queue verifier
  verify_live_validation_queue_safety.py live validation queue command safety verifier
  kube-actuary.live-validation-queue.v1 live validation queue schema
  prepare_live_evidence_directory.py live evidence directory scaffold generator with probe-aware next-task advancement
  kube-actuary.environment-probe.v1 environment probe report schema
  kube-actuary.environment-blockers.v1 environment blocker report schema
  run_next_version_task.py selected next-task plan/run/record helper
  verify_next_version_task_runner.py selected next-task runner verifier
  kube-actuary.next-version-task-run.v1 selected next-task runner schema
  next-version-task-run.json persisted selected runner status report
  advance_version_iteration.py selected next-task runner plus before/after history and runner status recorder
  verify_version_iteration_advance.py version iteration advance verifier
  kube-actuary.version-iteration-advance.v1 version iteration advance schema
  version-iteration-advance.json persisted advance workflow status report
  verify_live_evidence_directory_scaffold.py live evidence directory scaffold verifier
  validate_live_evidence.py   captured live evidence JSON validator
  verify_live_evidence_schema.py live evidence schema verifier
  build_live_evidence_manifest.py captured evidence manifest builder
  verify_live_evidence_manifest.py live evidence manifest verifier
  check_live_evidence_coverage.py live evidence release-gate coverage checker
  verify_live_evidence_coverage.py live evidence coverage verifier
  verify_project_governance.py contribution, notice, and license verifier
  generate_airgap_manifest.py air-gapped artifact manifest generator
  verify_airgap_bundle.py     offline bundle verifier
  verify_agent_help_contract.py agent help schema contract verifier
  verify_agent_examples.py    local CI/Codex runbook verifier
  adapt_kyverno_evidence.py   Kyverno output to evidence adapter
  verify_kyverno_adapter.py   Kyverno adapter fixture verifier
  adapt_opa_evidence.py       OPA output to evidence adapter
  verify_opa_adapter.py       OPA adapter fixture verifier
  adapt_kube_linter_evidence.py kube-linter output to evidence adapter
  verify_kube_linter_adapter.py kube-linter adapter fixture verifier
  adapt_kube_score_evidence.py kube-score output to evidence adapter
  verify_kube_score_adapter.py kube-score adapter fixture verifier
  adapt_pluto_evidence.py     Pluto output to evidence adapter
  verify_pluto_adapter.py     Pluto adapter fixture verifier
  verify_adapter_contract.py  common adapter contract verifier
  kube_actuary_mcp_server.py  safe MCP/JSON-RPC stdio wrapper
  verify_mcp_contract.py      MCP safe-tool contract verifier
  verify_mcp_docs.py          MCP docs and client config verifier
  verify_execute_disabled.py  disabled execute surface verifier
  verify_admission_webhook.py optional admission prototype verifier
  evaluate_admission_review.py offline admission policy evaluator
  verify_admission_policy.py AI identity/annotation admission verifier
  verify_admission_digest_gate.py admission digest/gate tamper verifier
  verify_admission_audit.py  admission audit fixture verifier
  verify_admission_response.py AdmissionReview response verifier
  verify_admission_server.py local admission HTTP server verifier
  run_admission_kind_smoke.py optional kind admission smoke harness
  verify_release.py            repeatable release verification suite
assets/brand/
  kubeactuary-symbol.png       selected project symbol
  symbol-option-*.svg          earlier symbol candidates
tests/
  test_cli.py                  CLI tests
```

## Development

No dependency install is required for the current CLI.

```sh
python3 -B -m unittest discover -s tests
python3 -B scripts/verify_release.py --version 0.2.0
python3 -B scripts/verify_release_taskboard.py
python3 -B scripts/verify_release_progress.py
python3 -B scripts/verify_version_worklist.py
python3 -B scripts/generate_version_worklist.py --format markdown --open-only
python3 -B scripts/generate_version_worklist.py --format markdown --open-only --evidence-dir evidence/live
python3 -B scripts/generate_version_worklist.py --format markdown --open-only --probe-environment
python3 -B scripts/generate_version_worklist.py --format json --version 0.4.3
python3 -B scripts/prepare_version_iteration.py /tmp/kubeactuary-version-iteration --version 0.4.3
python3 -B scripts/prepare_version_iteration.py /tmp/kubeactuary-version-iteration --open-only --evidence-dir evidence/live
python3 -B scripts/compare_version_iterations.py /tmp/kubeactuary-before /tmp/kubeactuary-after --format markdown
python3 -B scripts/record_version_iteration.py /tmp/kubeactuary-version-history --open-only --probe-environment
python3 -B scripts/record_version_iteration.py /tmp/kubeactuary-version-history --open-only --evidence-dir evidence/live
python3 -B scripts/inspect_version_history.py /tmp/kubeactuary-version-history
python3 -B scripts/select_next_version_task.py --version 0.4.3
python3 -B scripts/select_next_version_task.py --evidence-dir evidence/live
python3 -B scripts/select_next_version_task.py --evidence-dir evidence/live --skip-complete-evidence
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --skip-complete-evidence
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --probe-environment
python3 -B scripts/run_next_version_task.py evidence/live
python3 -B scripts/run_next_version_task.py evidence/live --run
python3 -B scripts/run_next_version_task.py evidence/live --run --record
python3 -B scripts/advance_version_iteration.py evidence/live /tmp/kubeactuary-version-history
python3 -B scripts/advance_version_iteration.py evidence/live /tmp/kubeactuary-version-history --run
python3 -B scripts/advance_version_iteration.py evidence/live /tmp/kubeactuary-version-history --probe-environment
python3 -B scripts/verify_external_gate_plan.py
python3 -B scripts/verify_external_gate_command_safety.py
python3 -B scripts/verify_external_gate_evidence.py
python3 -B scripts/verify_external_evidence_builder.py
python3 -B scripts/verify_external_evidence_bundle.py
python3 -B scripts/verify_release_evidence_directory.py
python3 -B scripts/verify_release_evidence_status.py
python3 -B scripts/verify_clean_artifacts.py
python3 -B bin/kube-actuary doctor
python3 -B scripts/verify_crd_compatibility.py
python3 -B scripts/verify_crd_explain_quality.py
python3 -B scripts/verify_conformance_suite.py
python3 -B scripts/verify_crd_upgrade_fixtures.py
python3 -B scripts/verify_controller_contract.py
python3 -B scripts/verify_controller_rbac.py
python3 -B scripts/verify_controller_runtime_contract.py
python3 -B scripts/verify_controller_deployment.py
python3 -B scripts/verify_controller_patch_plan.py
python3 -B scripts/verify_controller_sync.py
python3 -B scripts/verify_controller_status_apply.py
python3 -B scripts/verify_controller_loop.py
python3 -B scripts/verify_controller_resource_budget.py
python3 -B scripts/verify_lightweight_cluster_smoke.py
python3 -B scripts/verify_managed_kubernetes_smoke.py
python3 -B scripts/run_helm_smoke.py
python3 -B scripts/verify_helm_chart.py
python3 -B scripts/verify_kustomize.py
python3 -B scripts/verify_release_archives.py
python3 -B scripts/run_krew_smoke.py
python3 -B scripts/verify_krew_manifest.py
python3 -B scripts/verify_supply_chain.py
python3 -B scripts/verify_security_docs.py
python3 -B scripts/verify_api_freeze.py
python3 -B scripts/verify_docs_freeze.py
python3 -B scripts/verify_live_validation_readiness.py
python3 -B scripts/verify_live_validation_readiness.py --probe-environment
python3 -B scripts/generate_live_validation_queue.py --format markdown --probe-environment
python3 -B scripts/verify_live_validation_queue.py
python3 -B scripts/verify_live_validation_queue_safety.py
python3 -B scripts/verify_live_evidence_directory_scaffold.py
python3 -B scripts/verify_live_evidence_schema.py
python3 -B scripts/verify_live_evidence_manifest.py
python3 -B scripts/verify_live_evidence_coverage.py
python3 -B scripts/verify_project_governance.py
python3 -B scripts/verify_airgap_bundle.py
python3 -B scripts/verify_agent_help_contract.py
python3 -B scripts/verify_agent_examples.py
python3 -B scripts/verify_kyverno_adapter.py
python3 -B scripts/verify_opa_adapter.py
python3 -B scripts/verify_kube_linter_adapter.py
python3 -B scripts/verify_kube_score_adapter.py
python3 -B scripts/verify_pluto_adapter.py
python3 -B scripts/verify_adapter_contract.py
python3 -B scripts/verify_mcp_contract.py
python3 -B scripts/verify_mcp_docs.py
python3 -B scripts/verify_execute_disabled.py
python3 -B scripts/verify_admission_webhook.py
python3 -B scripts/verify_admission_policy.py
python3 -B scripts/verify_admission_digest_gate.py
python3 -B scripts/verify_admission_audit.py
python3 -B scripts/verify_admission_response.py
python3 -B scripts/verify_admission_server.py
python3 -B scripts/run_admission_kind_smoke.py
python3 -B scripts/generate_release_notes.py --version 0.2.0 --output -
```

Validate examples:

```sh
python3 -B bin/kube-actuary validate examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml charts/kubeactuary/Chart.yaml charts/kubeactuary/values.yaml deploy/kustomize/base/kustomization.yaml deploy/kustomize/overlays/controller-namespace/kustomization.yaml deploy/kustomize/overlays/controller-cluster/kustomization.yaml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml deploy/admission/validatingwebhookconfiguration.yaml
```

## Brand Proposals

Symbol candidates are in [docs/brand-options.md](docs/brand-options.md).

The recommended direction is a restrained cloud-native mark: a Kubernetes-like
operation ring, a proof check, and an actuarial/risk signal. Pick one before the
final logo is locked into the README header.

## Roadmap

Current v0.2.0:

- evidence collectors for auth, dry-run, diff, rollback, and health plans;
- local capsule structure validation;
- local runtime and kubectl client diagnostics;
- GitHub Actions CI and release notes dry-run tooling;
- versioned agent help compatibility contract;
- deterministic capsule spec digest;
- richer CRD rendering for local evidence workflows.
- CRD status condition mapping for local fixtures and future controller
  compatibility.
- offline CRD compatibility smoke for upstream Kubernetes N/N-1/N-2 and
  managed-service support notes.
- CRD upgrade and rollback fixtures with offline verification.
- kubectl explain descriptions and offline quality checks.
- pure low-overhead controller reconcile model, watch boundary, and read-only
  sync plan contract.
- Helm, Kustomize, release archive, and Krew manifest verification paths.

Later:

- minimal low-overhead controller;
- CRD status condition mapping;
- agent workflow examples;
- real Krew install validation;
- optional admission webhook for AI-originated writes;
- agent help contract versioning.

See [docs/roadmap.md](docs/roadmap.md).

## Status

v0.2.0 alpha. Useful as a local-first evidence collector workflow and
specification seed.
Not a production controller yet.

## License

MIT. See [LICENSE](LICENSE).

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution rules and
[NOTICE](NOTICE) for attribution status.
