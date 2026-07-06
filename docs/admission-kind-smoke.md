# Admission Kind Smoke

This runbook defines the optional v0.8.0 kind smoke path for admission checks.
The default command only prints the plan and does not contact a cluster.

## Plan Mode

```sh
python3 -B scripts/run_admission_kind_smoke.py
python3 -B scripts/run_admission_kind_smoke.py --output /tmp/kubeactuary-admission-kind-plan.json
```

Plan mode prints:

- `kubectl version --client=true -o json`;
- `kubectl apply --dry-run=server` for the optional webhook manifest;
- local admission policy fixture verification;
- local AdmissionReview response verification;
- local loopback admission server smoke.

## Run Mode

Run mode requires kubectl and a disposable or explicitly approved kind context:

```sh
python3 -B scripts/run_admission_kind_smoke.py --run --output /tmp/kubeactuary-admission-kind-smoke.json
```

The run does not persist the webhook. It uses Kubernetes server-side dry-run for
the webhook manifest and loopback-only checks for the local admission server.

The optional `--output` file uses `kube-actuary.admission-kind-smoke.v1` and
records `clusterWrites: server-side-dry-run-only`, `localServer:
loopback-only`, each command, exit code, and raw stdout/stderr. Keep this file
as admission kind smoke evidence when moving the admission webhook entry from
`VERIFY` to `DONE`.

## Offline Verification

```sh
python3 -B scripts/verify_admission_webhook.py
```

The verifier checks the webhook manifest and exercises the smoke runner with
fake kubectl. It does not require kind to be installed.
