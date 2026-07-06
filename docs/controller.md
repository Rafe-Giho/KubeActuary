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
- resource-budget contract and measurement harness.

Not implemented yet:

- in-cluster Deployment;
- live HTTP serving for probes and metrics;
- live Kubernetes watch loop;
- status patch write path.

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

The runtime contract is local and deterministic today. It does not contact a
cluster, start a server, or create a `Lease`.

Offline verifier:

```sh
python3 -B scripts/verify_controller_runtime_contract.py
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
```

The local verifier checks the budget contract and measurement parser with pass
and fail samples:

```sh
python3 -B scripts/verify_controller_resource_budget.py
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

## Future Status Patch Boundary

Future live controller work may patch only the `status` subresource of
`operationcapsules.ops.kubeactuary.dev`. It must not update `spec`, execute
`spec.proposedAction.command`, or mutate target workloads directly.
