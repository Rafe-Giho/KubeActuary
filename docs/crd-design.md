# OperationCapsule CRD Design

The CRD turns KubeActuary from a local file format into a Kubernetes-native
workflow.

## Goals

- Make AI-originated operation proposals visible as Kubernetes resources.
- Let RBAC, audit logs, GitOps, and status conditions work naturally.
- Keep resource overhead low.
- Avoid building a heavyweight in-cluster agent platform.

## Non-goals

- Do not run LLM inference inside the cluster.
- Do not watch every Kubernetes object.
- Do not execute proposed writes in the first controller version.
- Do not require every cluster to install admission webhooks.

## Resource Model

One primary CRD:

- `OperationCapsule.ops.kubeactuary.dev`

The CRD stores:

- intent
- actor
- proposed action
- target
- risk
- required evidence
- attached evidence summaries or references
- rollback plan
- status phase and conditions

Evidence stays embedded at first. A separate Evidence CRD can be added only if
real usage shows object size or sharing pressure.

## Low-Overhead Controller

The controller should:

- watch only `OperationCapsule` resources;
- requeue only on capsule changes or explicit TTL;
- compute missing and failed evidence;
- set `status.phase`;
- set conditions;
- avoid cluster-wide list/watch operations;
- avoid log/event scraping unless a future collector explicitly asks for it.

This makes the controller mostly idle in normal operation.

## Phases

- `Drafted`
- `EvidenceAttached`
- `GateOpen`
- `Blocked`
- `Expired`
- `Executed` future only

## Conditions

- `EvidenceComplete`
- `GateOpen`
- `RiskAccepted`
- `RollbackReady`
- `Expired`

## Security Model

Recommended RBAC:

- AI agents may create `OperationCapsule` resources.
- Evidence collectors may patch `status.evidence` or add evidence references.
- Human/platform reviewers may attach approval evidence.
- Only a future executor service account may execute approved capsules.

This separates proposal, evidence, approval, and execution.

