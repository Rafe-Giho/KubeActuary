# Lightweight Cluster Smoke

This runbook defines the repeatable v0.4.4 smoke path for kind, minikube,
MicroK8s, and k3s. It is intentionally conservative: the default command prints
the plan and does not contact a cluster.

## Providers

- kind
- minikube
- MicroK8s
- k3s

## Plan Mode

```sh
python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind
python3 -B scripts/run_lightweight_cluster_smoke.py --provider minikube
python3 -B scripts/run_lightweight_cluster_smoke.py --provider microk8s
python3 -B scripts/run_lightweight_cluster_smoke.py --provider k3s
```

Plan mode prints the exact `kubectl` commands that would be run.

## Run Mode

After starting the target cluster and selecting its kubeconfig context:

```sh
python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind --run
```

The run uses server-side dry-run for manifests:

```sh
kubectl apply --dry-run=server -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml
kubectl apply --dry-run=server -f deploy/controller/namespace-scoped-rbac.yaml
kubectl apply --dry-run=server -f deploy/controller/cluster-scoped-rbac.yaml
```

It also checks `kubectl auth can-i` boundaries and captures `kubectl top pod`
output for the controller resource-budget measurement. It does not apply
workloads, delete resources, run LLMs, or execute proposed Kubernetes writes.

Use `--kubectl` for wrappers such as `microk8s kubectl` exposed as a local
script.

## Offline Verification

```sh
python3 -B scripts/verify_lightweight_cluster_smoke.py
```

This verifies the smoke plan for all four providers. It does not replace live
matrix evidence.
