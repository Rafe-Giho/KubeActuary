# Project Assessment

Snapshot date: 2026-07-02.

## Current Maturity

KubeActuary is at an alpha seed stage moving toward v0.1.0.

What is real:

- local CLI exists and runs with only Python standard library;
- operation capsules can be drafted, inspected, verified, and gated;
- manual evidence can be attached;
- `kubectl auth can-i` evidence can be collected without executing the proposed
  operation;
- local capsule JSON can be rendered as a Kubernetes `OperationCapsule` CRD
  object;
- a CRD seed exists;
- tests cover the main local workflow.

What is not real yet:

- no controller;
- no admission webhook;
- no direct Kubernetes write execution;
- no live `kubectl diff` collector;
- no server-side dry-run collector;
- no policy adapters;
- no release packaging;
- no Krew manifest;
- no MCP server.

## Self-Evaluation

| Area | Score | Reason |
| --- | ---: | --- |
| Idea clarity | 8/10 | The evidence-carrying operation capsule model is clear and differentiated. |
| Local CLI utility | 7/10 | The local proposal/evidence/gate workflow works; more collectors are needed. |
| Kubernetes-native path | 6/10 | CRD seed and render flow exist; controller is not implemented yet. |
| Safety model | 8/10 | No direct write execution, model-free default, and evidence gate are explicit. |
| Documentation | 7/10 | README and design docs are now usable; contributor/release docs are still missing. |
| Test coverage | 6/10 | Core CLI paths are tested; schema and CRD semantic validation can improve. |
| Release readiness | 5/10 | v0.1.0 can be a usable alpha, not a production-ready controller. |

Overall: KubeActuary is good enough for a v0.1.0 alpha if the goal is a
local-first CLI and spec seed. It is not yet a cluster automation product.

## Next Work

Priority order:

1. Add `collect dry-run` for server-side dry-run evidence.
2. Add `collect diff` for `kubectl diff` evidence.
3. Add rollback evidence helpers.
4. Add capsule digest/signature support.
5. Add CRD status condition mapping.
6. Add a minimal read-only controller that watches only `OperationCapsule`.
7. Add Krew packaging.
8. Add MCP server wrapper for safe tools.
9. Add optional admission webhook for AI-originated write identities.
10. Add policy adapters for Kyverno, OPA, kube-linter, kube-score, and Pluto.

