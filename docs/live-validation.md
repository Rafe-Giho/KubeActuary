# Live Validation Readiness

This ledger tracks validation that cannot be honestly marked `DONE` from local
offline checks alone. The verifier is inventory-only: it checks local tool
availability and required documentation, but does not contact a cluster, does not contact cloud APIs, and does not create, update, or delete Kubernetes resources.

Run:

```sh
python3 -B scripts/verify_live_validation_readiness.py
python3 -B scripts/verify_live_validation_readiness.py --json
```

Expected:

```text
live-validation-readiness: passed
mode: inventory-only
cluster-writes: disabled
```

## Open Live Gates

| Gate | Current local evidence | Required live evidence |
| --- | --- | --- |
| CRD apply and explain smoke | offline CRD compatibility, upgrade, and explain checks | kind or minikube server-side dry-run plus `kubectl explain` output |
| Controller resource budget | parser and budget contract | `kubectl top pod --containers` sample under the target controller deployment |
| Lightweight cluster smoke | plan verifier for kind, minikube, MicroK8s, and k3s | successful run output for each provider |
| Helm install path | chart contract verifier | `helm template` and install smoke against a disposable cluster |
| Krew install path | manifest verifier | `kubectl krew install --manifest` smoke |
| Managed Kubernetes smoke | compatibility notes for providers | provider run evidence for EKS, GKE, and AKS |
| Admission webhook smoke | offline optional webhook verifier | kind admission request smoke with opt-in namespace |

## Evidence Rules

- Use disposable clusters or explicitly approved test clusters only.
- Prefer server-side dry-run for CRD, RBAC, and chart checks.
- Do not run proposed workload writes as part of KubeActuary validation.
- Attach raw command output, cluster version, tool version, and timestamp.
- Keep provider run evidence separate from offline verifier output.
- For lightweight cluster smoke runs, use
  `scripts/run_lightweight_cluster_smoke.py --run --output <path>` and keep the
  `kube-actuary.lightweight-smoke.v1` report.

Provider run evidence means captured output from the target provider or tool,
not a local assumption that the path should work.
