# Roadmap

KubeActuary should grow in small layers. Each layer must preserve the main
constraint: AI is not trusted with unbounded Kubernetes write execution.

The actionable local taskboard is maintained in
[release-taskboard.md](release-taskboard.md). Repeatable release verification is
run with:

```sh
python3 -B scripts/verify_release.py --version 0.2.0
```

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

Status: implemented as the v0.2.0 alpha target.

Add read-only or dry-run collectors:

- `collect auth`: run `kubectl auth can-i`. Implemented.
- `collect diff`: run `kubectl diff`. Implemented.
- `collect dry-run`: run server-side dry-run. Implemented.
- `collect rollback`: attach rollback command or manifest snapshot. Implemented.
- `collect health-plan`: produce post-check plan. Implemented.
- `digest`: print a deterministic capsule spec digest. Implemented.

These collectors should write evidence into capsules. They should not execute
the proposed write.

## v0.3: Kubernetes-Native CRD

Add a lightweight CRD:

- `OperationCapsule.ops.kubeactuary.dev`
- status conditions: `EvidenceComplete`, `GateOpen`, `Blocked`,
  `RollbackReady`, `Expired`
- final state TTL support through labels or a future controller

No separate `Evidence` CRD initially. Keep evidence embedded or referenced from
the capsule to reduce object count.

Current local progress:

- CRD field names for `spec`, embedded evidence, rollback, and status are
  frozen for the alpha contract.
- `render-crd` emits `status.phase`, `status.gate`, missing/failed evidence,
  digest, and condition mappings for local fixtures.
- `docs/kubernetes-compatibility.md` records the upstream N/N-1/N-2 target and
  managed-service support snapshot.
- `scripts/verify_crd_compatibility.py` performs offline CRD compatibility
  smoke checks. Live kind/minikube matrix validation remains follow-up work.
- CRD upgrade and rollback fixtures are available under `deploy/crds/fixtures/`
  with an offline verifier and runbook.
- The CRD includes OpenAPI descriptions for `kubectl explain`, with an offline
  explain-quality verifier and live smoke runbook.

## v0.4: Minimal Controller

Build a low-overhead controller that:

- watches only `OperationCapsule` resources;
- computes missing evidence;
- sets status phase and conditions;
- never scans the whole cluster;
- never calls an LLM;
- never executes writes by default.

Expected footprint: one small controller deployment, idle most of the time.

Current local progress:

- pure Python reconcile model computes OperationCapsule status from embedded
  evidence;
- dry-run `bin/kube-actuary-controller reconcile` prints status or status-only
  patch JSON for fixtures;
- `bin/kube-actuary-controller watch-command` documents the intended
  OperationCapsule-only watch boundary;
- `scripts/verify_controller_contract.py` checks the status patch and watch
  target offline;
- namespace-scoped and cluster-scoped RBAC manifests grant only OperationCapsule
  read/watch and status patch permissions;
- health, readiness, metrics, and leader-election payload contracts are
  deterministic and offline-verifiable;
- resource budget target is set to idle <50m CPU and <64Mi memory, with a
  `kubectl top` measurement harness for live cluster evidence;
- lightweight cluster smoke harness prints or runs the kind, minikube, MicroK8s,
  and k3s server-side dry-run plan;
- live controller process, HTTP serving, deployment manifests, status
  subresource writes, and live matrix evidence remain future work.

## v0.5: Packaging and Installation

Make KubeActuary installable as a Kubernetes tool:

- Helm chart seed packages the CRD and optional controller RBAC. Static
  verification is available; live `helm template` and install smoke remain
  follow-up work.
- Kustomize base and controller RBAC overlays render with `kubectl kustomize`.
- Multi-target release archives generate SHA-256 sidecars and pass install
  smoke checks.
- Krew manifest generation is available from release archives. Real Krew install
  validation remains follow-up work.
- SBOM, provenance, and air-gapped install docs remain follow-up work.

## v0.6: Policy Adapters

Add optional adapters:

- Kyverno CLI
- OPA/Rego
- kube-linter
- kube-score
- Pluto

Adapters should attach evidence, not replace the core gate.

## v0.7: MCP Server

Expose safe MCP tools:

- `draft_operation_capsule`
- `inspect_operation_capsule`
- `attach_operation_evidence`
- `verify_operation_capsule`
- `gate_operation_capsule`

Keep `execute_approved_capsule` disabled or experimental until the gate and
audit story is mature.

## v0.8: Admission and Audit

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
