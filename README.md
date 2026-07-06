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
controller/
  reconcile.py                 pure OperationCapsule status reconcile model
.github/workflows/
  ci.yml                       GitHub Actions verification workflow
charts/
  kubeactuary/                 Helm chart seed
deploy/crds/
  operationcapsules...yaml     CRD seed
  fixtures/                    CRD upgrade and rollback fixtures
deploy/controller/
  *-rbac.yaml                  optional controller RBAC manifests
deploy/kustomize/
  base/                        CRD-only Kustomize base
  overlays/                    optional controller RBAC overlays
docs/
  collectors.md                evidence collector contract
  landscape.md                 ecosystem research
  paradigm.md                  operating model
  project-assessment.md        maturity assessment
  release-checklist.md         release gate checklist
  release-taskboard.md         local v1.0 taskboard
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
schemas/
  operation-capsule...json     JSON Schema
scripts/
  generate_release_notes.py    release notes dry-run generator
  verify_crd_compatibility.py  offline CRD compatibility smoke check
  verify_crd_explain_quality.py offline kubectl explain quality check
  verify_crd_upgrade_fixtures.py offline CRD upgrade fixture check
  verify_controller_contract.py offline controller contract check
  verify_controller_rbac.py    offline controller RBAC check
  verify_controller_runtime_contract.py offline controller runtime check
  verify_controller_resource_budget.py offline controller resource budget check
  measure_controller_resources.py kubectl top budget measurement helper
  run_lightweight_cluster_smoke.py lightweight cluster smoke harness
  verify_lightweight_cluster_smoke.py offline smoke harness check
  verify_helm_chart.py        offline Helm chart contract check
  verify_kustomize.py         Kustomize render check
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
python3 -B bin/kube-actuary doctor
python3 -B scripts/verify_crd_compatibility.py
python3 -B scripts/verify_crd_explain_quality.py
python3 -B scripts/verify_crd_upgrade_fixtures.py
python3 -B scripts/verify_controller_contract.py
python3 -B scripts/verify_controller_rbac.py
python3 -B scripts/verify_controller_runtime_contract.py
python3 -B scripts/verify_controller_resource_budget.py
python3 -B scripts/verify_lightweight_cluster_smoke.py
python3 -B scripts/verify_helm_chart.py
python3 -B scripts/verify_kustomize.py
python3 -B scripts/generate_release_notes.py --version 0.2.0 --output -
```

Validate examples:

```sh
python3 -B bin/kube-actuary validate examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml charts/kubeactuary/Chart.yaml charts/kubeactuary/values.yaml deploy/kustomize/base/kustomization.yaml deploy/kustomize/overlays/controller-namespace/kustomization.yaml deploy/kustomize/overlays/controller-cluster/kustomization.yaml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml
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
- pure low-overhead controller reconcile model and watch boundary contract.

Later:

- minimal low-overhead controller;
- CRD status condition mapping;
- optional MCP server;
- Krew packaging;
- optional admission webhook for AI-originated writes;
- policy adapters for Kyverno, OPA, kube-linter, kube-score, and Pluto.

See [docs/roadmap.md](docs/roadmap.md).

## Status

v0.2.0 alpha. Useful as a local-first evidence collector workflow and
specification seed.
Not a production controller yet.

## License

MIT. See [LICENSE](LICENSE).
