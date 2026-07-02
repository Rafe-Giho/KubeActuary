# Conversation Captions

This file captures the working conversation that led to the current
KubeActuary project seed.

## Initial Request

The request was to search and learn from Kubernetes-related projects and CLIs,
then invent or plan an open-source Kubernetes tool that helps AI use Kubernetes
well and could contribute meaningfully to cloud native operations.

## Research Direction

We used authoritative ecosystem anchors:

- Kubernetes official kubectl plugin model.
- Krew plugin index.
- CNCF Landscape.
- Representative AI/Kubernetes tools such as `kubectl-ai`, `k8sgpt`, `kagent`,
  and Kubernetes MCP servers.
- Static analysis, policy, GitOps, and observability projects.

The observed gap was not another natural-language Kubernetes assistant. The
missing layer was an execution contract for AI-originated Kubernetes actions.

## Chosen Project

Name: KubeActuary.

Core idea:

AI should not operate Kubernetes through raw command execution. It should
produce an evidence-carrying `OperationCapsule` first. The capsule contains
intent, target, risk, required evidence, rollback, and post-change checks.
Execution is only a candidate when the gate opens.

## Novelty Discussion

The project does not claim to invent GitOps, policy engines, admission control,
MCP, or proof-carrying systems.

The narrow novelty claim is the synthesis:

Use a model-free, evidence-carrying operation capsule as the execution boundary
for AI-originated Kubernetes operations.

## CRD Discussion

A CRD can improve the quality of the idea by making it Kubernetes-native.

The lightweight direction is:

- Add one `OperationCapsule` CRD first.
- Let AI, CLI, CI, or GitOps create capsule resources.
- Let a small controller verify evidence and write status.
- Avoid cluster-wide scans.
- Avoid running LLMs in the cluster.
- Keep admission webhooks and direct execution for later versions.

This keeps resource overhead low while using Kubernetes-native RBAC, audit,
status conditions, and controller patterns.

## Current Working State

Implemented:

- CLI draft, inspect, verify, attach-evidence, gate, demo.
- Kubectl plugin entrypoint.
- JSON Schema for the capsule format.
- Example open and closed gates.
- Unit tests.
- Landscape, paradigm, novelty, interoperability, and completion audit docs.
- Initial CRD and CRD example manifests.

Not implemented yet:

- Live `kubectl auth can-i` evidence collector.
- Live `kubectl diff` collector.
- Server-side dry-run collector.
- Controller runtime implementation.
- MCP server wrapper.
- Krew packaging.
- Admission webhook.
- Signed capsule digests and tamper-evident audit logs.

