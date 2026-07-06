# Low-Overhead Controller

The controller remains optional. The default KubeActuary path is still local CLI
and evidence files.

## v0.4.0 to v0.4.2 Scope

Implemented locally:

- pure reconcile model for one `OperationCapsule` object;
- status patch generation for fake-client tests and future controller wiring;
- documented watch command that targets only `OperationCapsule` resources;
- namespace-scoped and cluster-scoped RBAC manifests;
- health, readiness, metrics, and leader-election payload contracts;
- local `serve` runtime for `/healthz`, `/readyz`, and `/metrics`;
- optional Deployment seed for the local runtime;
- dry-run status loop for repeated read/status-patch ticks;
- resource-budget contract and measurement harness.

Not implemented yet:

- streaming Kubernetes watch loop;
- default persistent status writes.

## Watch Boundary

The controller must watch only:

```sh
kubectl get operationcapsules.ops.kubeactuary.dev -o json --watch --all-namespaces
```

Namespace-scoped mode:

```sh
kubectl get operationcapsules.ops.kubeactuary.dev -o json --watch -n <namespace>
```

It must not watch Pods, Deployments, Nodes, Events, Namespaces, or arbitrary
cluster objects. It must not run LLMs or execute proposed Kubernetes writes.

## RBAC Boundary

Manifests:

```sh
deploy/controller/namespace-scoped-rbac.yaml
deploy/controller/cluster-scoped-rbac.yaml
```

Both modes grant only:

- `get`, `list`, `watch` on `operationcapsules.ops.kubeactuary.dev`;
- `get`, `patch`, `update` on `operationcapsules/status` in API group
  `ops.kubeactuary.dev`.

The controller RBAC must not grant workload, node, event, secret, configmap,
wildcard resource, wildcard API group, create, delete, or main-resource update
permissions.

Offline verifier:

```sh
python3 -B scripts/verify_controller_rbac.py
```

## Runtime Boundary

Dry-run helpers:

```sh
python3 bin/kube-actuary-controller health
python3 bin/kube-actuary-controller ready
python3 bin/kube-actuary-controller metrics
python3 bin/kube-actuary-controller leader-election
```

Future live controller wiring should expose:

- `/healthz` from the `health` payload;
- `/readyz` from the `ready` payload;
- `/metrics` using the Prometheus text emitted by `metrics`;
- leader election with Kubernetes `Lease` objects from
  `leases.coordination.k8s.io`.

The runtime contract verifier is local and deterministic today. It does not
contact a cluster, start a server, or create a `Lease`.

Offline verifier:

```sh
python3 -B scripts/verify_controller_runtime_contract.py
```

## Deployment Seed

The optional Deployment seed runs the local `serve` runtime only:

```sh
python3 bin/kube-actuary-controller serve --host 0.0.0.0 --port 8080
```

It exposes:

- `/healthz`
- `/readyz`
- `/metrics`

Manifests:

```sh
deploy/controller/deployment.yaml
charts/kubeactuary/templates/controller-deployment.yaml
deploy/kustomize/overlays/controller-namespace/controller/deployment.yaml
deploy/kustomize/overlays/controller-cluster/controller/deployment.yaml
```

The Deployment seed sets `automountServiceAccountToken: false`, runs as
non-root, drops Linux capabilities, and keeps the resource limits at `50m` CPU
and `64Mi` memory. It does not run a live Kubernetes watch loop yet.

Offline verifier:

```sh
python3 -B scripts/verify_controller_deployment.py
```

## Resource Budget

Target:

- idle <50m CPU;
- <64Mi memory.

Dry-run budget contract:

```sh
python3 bin/kube-actuary-controller resource-budget
python3 bin/kube-actuary-controller measure-command
```

Measurement helper:

```sh
python3 -B scripts/measure_controller_resources.py
```

The helper evaluates `kubectl top pod --containers` output against the budget.
It can also evaluate captured samples:

```sh
python3 -B scripts/measure_controller_resources.py --sample kubectl-top.txt
python3 -B scripts/measure_controller_resources.py --sample kubectl-top.txt --format json
```

The JSON format uses schema `kube-actuary.controller-resource-measurement.v1`
and records observed maxima, sample count, and budget limits for supplemental
evidence. The local verifier checks the budget contract and measurement parser
with pass and fail samples:

```sh
python3 -B scripts/verify_controller_resource_budget.py
```

Live evidence capture uses a plan-by-default wrapper and runs only the read-only
`kubectl top pod --containers` command when `--run` is set:

```sh
python3 -B scripts/capture_controller_resource_budget.py --output evidence/live/raw/01-controller-resource-budget-kubectl-top.txt
python3 -B scripts/capture_controller_resource_budget.py --output evidence/live/raw/01-controller-resource-budget-kubectl-top.txt --run
python3 -B scripts/build_external_evidence.py --kind controller-resource-budget --source evidence/live/raw/01-controller-resource-budget-kubectl-top.txt --output evidence/live/supplemental/01-controller-resource-budget-external-2.json
```

Live kind, minikube, MicroK8s, and k3s measurements are still required before
claiming measured controller footprint.

## Dry-Run Reconcile

```sh
python3 bin/kube-actuary-controller reconcile operationcapsule.json
python3 bin/kube-actuary-controller reconcile operationcapsule.json --format patch
python3 bin/kube-actuary-controller watch-command
```

The reconcile command reads one OperationCapsule JSON object and emits derived
status. It does not contact a cluster.

Derived fields:

- `status.phase`
- `status.gate`
- `status.missingEvidence`
- `status.failedEvidence`
- `status.digest`
- `status.conditions`

## Status Patch Boundary

Controller status work may patch only the `status` subresource of
`operationcapsules.ops.kubeactuary.dev`. It must not update `spec`, execute
`spec.proposedAction.command`, or mutate target workloads directly.

## Status Patch Plan

The local patch planner computes status-only patch payloads for one
`OperationCapsule` object or a Kubernetes list. It does not execute the patch:

```sh
python3 bin/kube-actuary-controller patch-plan operationcapsules.json
python3 bin/kube-actuary-controller patch-plan operationcapsules.json --format commands
```

The generated command shape is limited to:

```sh
kubectl patch operationcapsules.ops.kubeactuary.dev <name> --type merge --subresource status -p <status-only-patch>
```

The JSON output includes `writeExecution: disabled`, and each patch body has
only a top-level `status` field.

Offline verifier:

```sh
python3 -B scripts/verify_controller_patch_plan.py
```

## Read-Only Sync

The optional `sync` helper performs one read-only list call, then emits the same
status patch plan contract. It does not execute any generated patch command:

```sh
python3 bin/kube-actuary-controller sync
python3 bin/kube-actuary-controller sync --namespace platform
```

The only Kubernetes command it runs is:

```sh
kubectl get operationcapsules.ops.kubeactuary.dev -o json --all-namespaces
```

or the namespace-scoped equivalent with `-n <namespace>`. The JSON output
includes `readExecution: kubectl-get`, the exact `readCommand`,
`writeExecution: disabled`, and status-only patch plans.

Offline verifier:

```sh
python3 -B scripts/verify_controller_sync.py
```

## Status Loop

The optional `loop` helper repeats the same read/status-patch sequence. It is
dry-run by default: each generated patch command includes `--dry-run=server`.

```sh
python3 bin/kube-actuary-controller loop --iterations 2 --interval-seconds 0
python3 bin/kube-actuary-controller loop --namespace platform
```

The finite JSON output includes `readExecution: kubectl-get`,
`writeExecution: disabled`, `patchScope: status`, the iteration count, and the
per-tick status patch dry-run results. An infinite loop is available only with
streaming output:

```sh
python3 bin/kube-actuary-controller loop --iterations 0 --format ndjson
```

Persistent status writes require the explicit `--execute` flag and remain
status-only:

```sh
python3 bin/kube-actuary-controller loop --execute
```

Offline verifier:

```sh
python3 -B scripts/verify_controller_loop.py
```

## Status Apply Dry-Run

`apply-status` is the first execution-shaped helper for status patches. Its
default mode is still non-persistent: it adds `--dry-run=server` to every
generated `kubectl patch` command.

```sh
python3 bin/kube-actuary-controller apply-status operationcapsules.json
```

The command may patch only the `status` subresource of
`operationcapsules.ops.kubeactuary.dev`. It must not mutate `spec`, execute a
capsule's proposed workload command, or apply/delete workload resources.

Live status writes require an explicit flag:

```sh
python3 bin/kube-actuary-controller apply-status operationcapsules.json --execute
```

That mode is status-only but persistent. Keep it behind live validation and RBAC
gates; it is not part of the default local release path.

Offline verifier:

```sh
python3 -B scripts/verify_controller_status_apply.py
```
