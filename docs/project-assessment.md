# Project Assessment

Snapshot date: 2026-07-05.

## Current Maturity

KubeActuary is at an alpha seed stage moving toward v0.2.0.

What is real:

- local CLI exists and runs with only Python standard library;
- operation capsules can be drafted, inspected, verified, and gated;
- manual evidence can be attached;
- `kubectl auth can-i` evidence can be collected without executing the proposed
  operation;
- server-side dry-run and `kubectl diff` evidence can be collected for
  manifest-based operations;
- rollback command/manifest and health-plan evidence can be attached;
- deterministic capsule spec digests can be printed and added to rendered CRD
  annotations;
- local capsule JSON can be rendered as a Kubernetes `OperationCapsule` CRD
  object;
- a CRD seed exists;
- tests cover the main local workflow.

What is not real yet:

- no controller;
- no admission webhook;
- no direct Kubernetes write execution;
- no policy adapters;
- no release packaging;
- no Krew manifest;
- no MCP server.

## Self-Evaluation

| Area | Score | Reason |
| --- | ---: | --- |
| Idea clarity | 8/10 | The evidence-carrying operation capsule model is clear and differentiated. |
| Local CLI utility | 8/10 | The local proposal/evidence/gate workflow has the core v0.2 collectors. |
| Kubernetes-native path | 6/10 | CRD seed and render flow exist; controller is not implemented yet. |
| Safety model | 8/10 | No direct write execution, model-free default, and evidence gate are explicit. |
| Documentation | 7/10 | README and design docs are now usable; contributor/release docs are still missing. |
| Test coverage | 7/10 | Core CLI and collector paths are tested; schema and CRD semantic validation can improve. |
| Release readiness | 6/10 | v0.2.0 can be a useful local/CI alpha, not a production-ready controller. |

Overall: KubeActuary is good enough for a v0.2.0 alpha if the goal is a
local-first evidence collector CLI and spec seed. It is not yet a cluster
automation product.

## Next Work

Priority order:

1. Add CRD status condition mapping.
2. Add a minimal read-only controller that watches only `OperationCapsule`.
3. Add Krew packaging.
4. Add MCP server wrapper for safe tools.
5. Add optional admission webhook for AI-originated write identities.
6. Add policy adapters for Kyverno, OPA, kube-linter, kube-score, and Pluto.
7. Add signature support on top of deterministic capsule digests.
