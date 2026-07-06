# Helm Smoke

This runbook defines the v0.5.0 Helm chart smoke path. The default command only
prints the plan and does not contact a cluster.

## Plan Mode

```sh
python3 -B scripts/run_helm_smoke.py
python3 -B scripts/run_helm_smoke.py --output /tmp/kubeactuary-helm-plan.json
```

Plan mode prints:

- `helm template` with the controller disabled;
- `helm template` with the controller enabled;
- `kubectl apply --dry-run=server` for the chart CRD;
- `helm install --dry-run --debug` with the controller enabled.

## Run Mode

Run mode requires Helm, kubectl, and a disposable or explicitly approved test
cluster context:

```sh
python3 -B scripts/run_helm_smoke.py --run --output /tmp/kubeactuary-helm-smoke.json
```

The run does not persist chart resources. It uses Helm dry-run and Kubernetes
server-side dry-run checks only.

The optional `--output` file uses `kube-actuary.helm-smoke.v1` and records the
release name, namespace, chart, mode, `clusterWrites: dry-run-only`, each
command, exit code, and raw stdout/stderr. Keep this file as Helm install path
evidence when moving the Helm chart entry from `VERIFY` to `DONE`.

## Offline Verification

```sh
python3 -B scripts/verify_helm_chart.py
```

The verifier checks the chart contract and exercises the smoke runner with fake
Helm and kubectl binaries. It does not require Helm to be installed.
