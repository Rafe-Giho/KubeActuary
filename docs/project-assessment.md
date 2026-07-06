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
- Helm, Kustomize, release archive, and Krew manifest generation paths exist
  with offline verifiers;
- tests cover the main local workflow.

What is not real yet:

- no controller;
- no admission webhook;
- no direct Kubernetes write execution;
- no live Helm/Krew install validation;
- no production MCP packaging or client install guide.

## Self-Evaluation

| Area | Score | Reason |
| --- | ---: | --- |
| Idea clarity | 8/10 | The evidence-carrying operation capsule model is clear and differentiated. |
| Local CLI utility | 8/10 | The local proposal/evidence/gate workflow has the core v0.2 collectors. |
| Kubernetes-native path | 7/10 | CRD, render flow, controller contracts, RBAC, and packaging paths exist; live controller is not deployed. |
| Safety model | 8/10 | No direct write execution, model-free default, and evidence gate are explicit. |
| Documentation | 7/10 | README and design docs are now usable; contributor/release docs are still missing. |
| Test coverage | 7/10 | Core CLI and collector paths are tested; schema and CRD semantic validation can improve. |
| Release readiness | 7/10 | v0.2.0 has repeatable local release checks and packaging seeds, but live install validation remains. |

Overall: KubeActuary is good enough for a v0.2.0 alpha if the goal is a
local-first evidence collector CLI and spec seed. It is not yet a cluster
automation product.

## Next Work

Priority order:

1. Add live install validation for Helm, Krew, and lightweight clusters.
2. Add a minimal read-only controller that watches only `OperationCapsule`.
3. Add release signing on top of deterministic digests and provenance.
4. Add MCP client install guidance and agent workflow examples.
5. Add optional admission webhook for AI-originated write identities.
6. Add richer adapter remediation hints and source excerpts.
7. Add signature support on top of deterministic capsule digests.
