# KubeActuary

> Evidence-carrying operations for AI-assisted Kubernetes.

[![Version](https://img.shields.io/badge/version-0.9.5-blue)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB)](bin/kube-actuary)
[![Kubernetes](https://img.shields.io/badge/kubernetes-OperationCapsule-326CE5)](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)

English | [한국어](README.ko.md)

KubeActuary is a local-first CLI for turning a proposed Kubernetes operation
into an auditable `OperationCapsule`. A capsule records the operation intent,
target, proposed command or manifest, risk, required evidence, collected
evidence, rollback basis, post-change check plan, and gate decision.

The tool is designed for AI-assisted Kubernetes workflows, but it does not trust
an AI agent just because it can produce a `kubectl` command. KubeActuary keeps
proposal, evidence, approval, and execution separate. The default CLI path
collects and verifies evidence; it does not execute direct cluster writes.

## Why It Exists

AI and automation tools can already generate Kubernetes actions. The missing
piece is a small, portable contract for deciding whether a proposed action has
enough proof before anything changes.

KubeActuary provides that contract:

- capture operation intent in a structured file;
- identify target scope and basic risk;
- collect safe evidence such as authorization, server dry-run, diff, rollback,
  and health-plan records;
- keep a deterministic digest of the operation spec;
- open the gate only when required evidence is present and successful;
- render the same local capsule as a Kubernetes `OperationCapsule` resource.

## Current Release

v0.9.5 is a pre-GA, local-complete CLI release. It reflects the public
repository scope: the CLI, capsule schema, CRD seed, manifest preflight
collectors, explicit rollback and health-plan evidence, deterministic digests,
offline verification, example capsules, and low-overhead controller design are
present and testable from the checked-in tree.

This is still not a 1.0.0 production claim. The remaining 1.0.0 work is live
evidence capture on approved Kubernetes and provider environments, including
cluster smoke runs, installation proof, managed-provider checks, public CI
evidence, and resource-budget evidence. Those checks are intentionally blocked
in environments without the required tools or network access.

What is included:

- local CLI and `kubectl` plugin entrypoint;
- JSON `OperationCapsule` format and schema;
- Kubernetes CRD seed for `OperationCapsule`;
- manifest preflight collectors for server-side dry-run and diff;
- explicit rollback and health-plan evidence;
- deterministic digest output;
- offline validation, verification, and gate decisions;
- low-overhead controller reconcile model with status-only boundaries;
- Helm chart seed, Kustomize assets, and optional deployment manifests;
- optional admission manifest prototype;
- agent-readable help for safer tool integration.

What is intentionally not included in the default path:

- no direct cluster write execution;
- no in-cluster LLM;
- no cluster-wide scan;
- no required controller;
- no required admission webhook;
- no external Python package dependency.

Release boundary:

- `0.9.5`: local implementation and offline contracts are present.
- `1.0.0`: requires external live evidence and green public CI before a GA
  claim.

## Installation

Clone the repository and run the CLI with Python:

```sh
git clone https://github.com/Rafe-Giho/KubeActuary.git
cd KubeActuary
python3 bin/kube-actuary --version
```

Use it as a `kubectl` plugin by putting `bin/` on `PATH`:

```sh
export PATH="$PWD/bin:$PATH"
kubectl actuary --version
```

No Python package installation is required for the current CLI.

## Quick Start

Verify and gate an included read-only example:

```sh
python3 bin/kube-actuary verify examples/read-pods.verified.capsule.json
python3 bin/kube-actuary gate examples/read-pods.verified.capsule.json
```

Expected gate result:

```text
gate: open
id: opcap-example-read-pods
risk: low
command: kubectl get pods -n default
```

Draft a higher-risk proposal. This command records the proposed operation; it
does not run the embedded `kubectl scale` command.

```sh
python3 bin/kube-actuary draft \
  --intent "increase checkout API capacity for expected traffic" \
  --command "kubectl scale deployment checkout-api --replicas=6 -n prod" \
  --actor "ai-agent" \
  --out /tmp/scale.capsule.json
```

Inspect and validate the capsule:

```sh
python3 bin/kube-actuary inspect /tmp/scale.capsule.json
python3 bin/kube-actuary validate /tmp/scale.capsule.json
```

Attach human approval evidence:

```sh
python3 bin/kube-actuary attach-evidence /tmp/scale.capsule.json \
  --id owner-approval \
  --summary "checkout service owner approved the scale-up window" \
  --actor "platform-reviewer" \
  --out /tmp/scale.with-approval.json
```

Collect authorization evidence without running the proposed write:

```sh
python3 bin/kube-actuary collect auth /tmp/scale.with-approval.json \
  --out /tmp/scale.with-auth.json
```

Verify the evidence set and print the gate decision:

```sh
python3 bin/kube-actuary verify /tmp/scale.with-auth.json
python3 bin/kube-actuary gate /tmp/scale.with-auth.json
```

## Manifest Preflight

For manifest-based operations, KubeActuary can collect Kubernetes preflight
evidence. These collectors may contact the configured cluster, but they are
evidence-only operations.

```sh
python3 bin/kube-actuary draft \
  --intent "apply demo config map" \
  --manifest examples/configmap-demo.yaml \
  --actor "ai-agent" \
  --out /tmp/apply.capsule.json

python3 bin/kube-actuary collect dry-run /tmp/apply.capsule.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-dry-run.json

python3 bin/kube-actuary collect diff /tmp/apply.with-dry-run.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-diff.json

python3 bin/kube-actuary collect rollback /tmp/apply.with-diff.json \
  --manifest examples/configmap-demo.rollback.yaml \
  --out /tmp/apply.with-rollback.json

python3 bin/kube-actuary collect health-plan /tmp/apply.with-rollback.json \
  --out /tmp/apply.ready.json
```

`collect dry-run` uses `kubectl apply --dry-run=server`. `collect diff` uses
`kubectl diff`. Both attach evidence to the capsule instead of applying a
change.

## OperationCapsule

An `OperationCapsule` is the core record KubeActuary works with.

| Section | Purpose |
| --- | --- |
| `metadata` | Capsule id, creation time, and actor information |
| `spec.intent` | Why the operation exists |
| `spec.proposedCommand` or `spec.manifest` | What is being proposed |
| `spec.target` | Kubernetes verb, resource, namespace, and scope |
| `spec.risk` | Basic risk and blast-radius classification |
| `spec.requiredEvidence` | Evidence required before the gate can open |
| `status.evidence` | Attached evidence records and collector results |
| `status.gate` | Open or closed decision with reasons |

The digest command hashes the operation spec while excluding status evidence, so
the same operation intent keeps the same digest even as evidence is attached:

```sh
python3 bin/kube-actuary digest examples/apply-configmap.preflight.capsule.json
```

## Commands

| Command | Purpose |
| --- | --- |
| `draft` | Create an operation capsule from intent plus command or manifest |
| `inspect` | Summarize target, risk, state, and evidence |
| `validate` | Validate capsule JSON structure |
| `doctor` | Check local runtime and `kubectl` client diagnostics |
| `attach-evidence` | Attach manual evidence |
| `collect auth` | Collect `kubectl auth can-i` evidence |
| `collect dry-run` | Attach server-side dry-run evidence |
| `collect diff` | Attach `kubectl diff` evidence |
| `collect rollback` | Attach explicit rollback command or manifest evidence |
| `collect health-plan` | Attach a declared post-change check plan |
| `digest` | Print a deterministic capsule spec digest |
| `verify` | Check required evidence |
| `gate` | Print the open or closed gate decision |
| `render-crd` | Render a local capsule as a Kubernetes resource |
| `demo` | Print a sample high-risk capsule |
| `help` | Show workflow, safety, evidence, or agent guidance |

Agent-readable help is available for integrations:

```sh
python3 bin/kube-actuary help agents --format json
```

## Kubernetes-Native Path

The repository includes a CRD seed and examples for teams that want to store
capsules in Kubernetes:

- [deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)
- [examples/operationcapsule-scale.yaml](examples/operationcapsule-scale.yaml)

Render a local capsule as a Kubernetes object:

```sh
python3 bin/kube-actuary render-crd examples/read-pods.verified.capsule.json \
  --name read-pods \
  --namespace default
```

The CRD path is intentionally low overhead: one namespaced
`OperationCapsule` resource, embedded evidence, status-friendly fields, and no
cluster-wide scan requirement.

## Safety Model

KubeActuary separates responsibilities instead of collapsing them into one
agent action.

| Responsibility | Typical actor |
| --- | --- |
| Proposal | AI agent, human, CI |
| Evidence collection | CLI, CI, policy tools |
| Approval | Human owner or platform reviewer |
| Gate decision | KubeActuary verification |
| Execution | Human, GitOps, or a future bounded executor |

The gate is a decision boundary. A closed gate means the operation should not
proceed because required evidence is missing or failed.

## Project Layout

```text
bin/                  CLI and kubectl plugin entrypoints
charts/               Helm chart seed
controller/           Low-overhead controller reconcile model
deploy/               CRD, optional controller, admission, and Kustomize assets
docs/                 Design notes, runbooks, compatibility, and roadmap
examples/             Capsule, manifest, CRD, and CLI-agent workflow examples
schemas/              JSON Schema and API freeze contract
tests/                CLI and behavior tests
```

## Documentation

- [Collectors](docs/collectors.md)
- [CRD design](docs/crd-design.md)
- [Kubernetes compatibility](docs/kubernetes-compatibility.md)
- [Controller design](docs/controller.md)
- [Security policy](SECURITY.md)
- [Threat model](docs/threat-model.md)
- [Roadmap](docs/roadmap.md)

## Development

Run the unit test suite:

```sh
python3 -B -m unittest discover -s tests
```

Contribution rules and safety expectations are documented in
[CONTRIBUTING.md](CONTRIBUTING.md). Security reporting is documented in
[SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
