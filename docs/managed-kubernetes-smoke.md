# Managed Kubernetes Smoke

This runbook defines the v0.9.0 managed Kubernetes smoke path for EKS, GKE, and
AKS. The default command only prints the plan and does not contact a cluster or
cloud API.

## Plan Mode

```sh
python3 -B scripts/run_managed_kubernetes_smoke.py --provider eks
python3 -B scripts/run_managed_kubernetes_smoke.py --provider gke
python3 -B scripts/run_managed_kubernetes_smoke.py --provider aks
```

Plan mode prints provider CLI version checks, kubectl client/server checks,
CRD server-side dry-run, `kubectl explain`, and OperationCapsule RBAC checks.

## Run Mode

Run mode requires an explicitly approved current kubeconfig context for the
target provider. It does not create clusters, fetch credentials, mutate
kubeconfig, or run provider cloud API calls beyond provider CLI version output.

```sh
python3 -B scripts/run_managed_kubernetes_smoke.py --provider eks --run --output /tmp/kubeactuary-eks-smoke.json
python3 -B scripts/run_managed_kubernetes_smoke.py --provider gke --run --output /tmp/kubeactuary-gke-smoke.json
python3 -B scripts/run_managed_kubernetes_smoke.py --provider aks --run --output /tmp/kubeactuary-aks-smoke.json
```

The Kubernetes write-shaped check is limited to:

```sh
kubectl apply --dry-run=server -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml
```

The optional `--output` file uses
`kube-actuary.managed-kubernetes-smoke.v1` and records the provider,
`clusterAccess: current-context`, `clusterWrites: server-side-dry-run-only`,
`cloudApi: version-command-only`, each command, exit code, and raw
stdout/stderr. Keep one report per provider as managed Kubernetes evidence when
moving the EKS/GKE/AKS smoke entry from `VERIFY` to `DONE`.

Use `--provider-cli` and `--kubectl` when the provider or kubectl binary is
wrapped by local tooling.

## Offline Verification

```sh
python3 -B scripts/verify_managed_kubernetes_smoke.py
```

The verifier checks plans and fake-tool evidence output for all three providers.
It does not require AWS, gcloud, Azure, kubectl server access, or cloud
credentials.
