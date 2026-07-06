# Admission Incident Runbook

Use this runbook when an AI-originated Kubernetes write was allowed or denied by
the optional KubeActuary admission path.

Required audit annotations:

- `kubeactuary.dev/capsule`
- `kubeactuary.dev/capsule-digest`
- `kubeactuary.dev/gate`
- `kubeactuary.dev/decision`
- `kubeactuary.dev/reason`

Triage steps:

1. Read the admission audit annotations from the Kubernetes audit event.
2. Locate the referenced OperationCapsule by `kubeactuary.dev/capsule`.
3. Run `python3 -B bin/kube-actuary digest <capsule>` and compare it with
   `kubeactuary.dev/capsule-digest`.
4. Run `python3 -B bin/kube-actuary gate <capsule>` and compare it with
   `kubeactuary.dev/gate`.
5. Run `python3 -B bin/kube-actuary inspect <capsule>` to review target, risk,
   evidence, and failed or missing requirements.
6. Preserve the capsule, admission review, and audit event as incident
   evidence.

Do not retry or apply the proposed Kubernetes write from this runbook. The
external operator or GitOps path remains responsible for any remediation.
