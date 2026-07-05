# KubeActuary

<p align="center">
  <img src="assets/brand/kubeactuary-symbol.png" alt="KubeActuary symbol" width="180">
</p>

> Evidence-carrying operations for AI-assisted Kubernetes.

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](VERSION)
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

## What Works in v0.1.0

- Draft local operation capsules from `kubectl` commands or manifest paths.
- Inspect target, risk, state, and evidence.
- Attach manual evidence.
- Collect `kubectl auth can-i` evidence.
- Verify missing or failed evidence.
- Open or close an execution gate.
- Render a local capsule as a Kubernetes `OperationCapsule` CRD object.
- Use the CLI as a `kubectl` plugin.
- Validate against a JSON Schema and CRD seed.

Non-goals for v0.1.0:

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
attach-evidence    Attach manual evidence
collect auth       Collect kubectl auth can-i evidence
verify             Check required evidence
gate               Print open/closed execution decision
render-crd         Render a capsule as a Kubernetes CRD object
demo               Print a sample high-risk capsule
```

Version:

```sh
python3 bin/kube-actuary --version
```

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
  kubectl-actuary              kubectl plugin entrypoint
deploy/crds/
  operationcapsules...yaml     CRD seed
docs/
  collectors.md                evidence collector contract
  landscape.md                 ecosystem research
  paradigm.md                  operating model
  project-assessment.md        maturity assessment
  roadmap.md                   development plan
  v0.1.0.md                    alpha release goal
  test-plan-v0.1.0.md          release test plan
  test-results-v0.1.0.md       latest verification result
  crd-design.md                Kubernetes-native design
  interoperability.md          CLI, MCP, GitOps, admission contracts
  novelty-check.md             novelty boundary
examples/
  *.capsule.json               local capsule examples
  operationcapsule-scale.yaml  CRD example
schemas/
  operation-capsule...json     JSON Schema
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
```

Validate examples:

```sh
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; YAML.load_file("deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"); puts "yaml ok"'
```

## Brand Proposals

Symbol candidates are in [docs/brand-options.md](docs/brand-options.md).

The recommended direction is a restrained cloud-native mark: a Kubernetes-like
operation ring, a proof check, and an actuarial/risk signal. Pick one before the
final logo is locked into the README header.

## Roadmap

Near-term:

- `collect dry-run` for server-side dry-run evidence;
- `collect diff` for `kubectl diff` evidence;
- rollback evidence helpers;
- capsule digest/signature support;
- CRD status condition mapping.

Later:

- minimal low-overhead controller;
- optional MCP server;
- Krew packaging;
- optional admission webhook for AI-originated writes;
- policy adapters for Kyverno, OPA, kube-linter, kube-score, and Pluto.

See [docs/roadmap.md](docs/roadmap.md).

## Status

v0.1.0 alpha. Useful as a local-first evidence workflow and specification seed.
Not a production controller yet.

## License

MIT. See [LICENSE](LICENSE).
