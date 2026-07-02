# Roadmap

KubeActuary should grow in small layers. Each layer must preserve the main
constraint: AI is not trusted with unbounded Kubernetes write execution.

## v0.1: Local Capsule CLI

Status: implemented as the v0.1.0 alpha target.

- Draft operation capsules from commands or manifest paths.
- Inspect target, risk, and evidence state.
- Attach evidence records.
- Collect auth evidence.
- Verify required evidence.
- Open or close an execution gate.
- Render local capsules as CRD objects.
- Publish JSON Schema.

## v0.2: Evidence Collectors

Status: started. `collect auth` is implemented.

Add read-only or dry-run collectors:

- `collect auth`: run `kubectl auth can-i`. Implemented.
- `collect diff`: run `kubectl diff`.
- `collect dry-run`: run server-side dry-run.
- `collect rollback`: attach rollback command or manifest snapshot.
- `collect health-plan`: produce post-check plan.

These collectors should write evidence into capsules. They should not execute
the proposed write.

## v0.3: Kubernetes-Native CRD

Add a lightweight CRD:

- `OperationCapsule.ops.kubeactuary.dev`
- status conditions: `EvidenceComplete`, `GateOpen`, `Blocked`, `Expired`
- final state TTL support through labels or a future controller

No separate `Evidence` CRD initially. Keep evidence embedded or referenced from
the capsule to reduce object count.

## v0.4: Minimal Controller

Build a low-overhead controller that:

- watches only `OperationCapsule` resources;
- computes missing evidence;
- sets status phase and conditions;
- never scans the whole cluster;
- never calls an LLM;
- never executes writes by default.

Expected footprint: one small controller deployment, idle most of the time.

## v0.5: Policy Adapters

Add optional adapters:

- Kyverno CLI
- OPA/Rego
- kube-linter
- kube-score
- Pluto

Adapters should attach evidence, not replace the core gate.

## v0.6: MCP Server

Expose safe MCP tools:

- `draft_operation_capsule`
- `inspect_operation_capsule`
- `attach_operation_evidence`
- `verify_operation_capsule`
- `gate_operation_capsule`

Keep `execute_approved_capsule` disabled or experimental until the gate and
audit story is mature.

## v0.7: Admission and Audit

Add optional admission controls:

- require capsule references for AI-originated write identities;
- verify capsule digest;
- enforce `GateOpen`;
- record audit annotations.

This should be optional because admission webhooks add operational risk.

## v1.0 Direction

KubeActuary becomes a small standard for evidence-carrying Kubernetes
operations:

- CLI for local and CI workflows.
- CRD for cluster-native workflows.
- MCP wrapper for AI tools.
- GitOps-friendly audit artifacts.
- Controller and admission components remain optional.
