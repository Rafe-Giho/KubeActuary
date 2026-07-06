# kubectl explain Quality Checks

KubeActuary's CRD should be readable through `kubectl explain`. The alpha CRD
uses OpenAPI descriptions for the fields that an operator is most likely to
inspect during review.

## Offline Check

```sh
python3 -B scripts/verify_crd_explain_quality.py
```

Expected:

```text
crd-explain-quality: passed
```

## Live Cluster Smoke

Use a disposable cluster:

```sh
kubectl apply --server-side \
  -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml

kubectl explain operationcapsule
kubectl explain operationcapsule.spec
kubectl explain operationcapsule.spec.proposedAction
kubectl explain operationcapsule.spec.evidence
kubectl explain operationcapsule.spec.rollback
kubectl explain operationcapsule.status
kubectl explain operationcapsule.status.conditions
```

Expected quality:

- root explain output describes an evidence-carrying Kubernetes operation;
- `spec` describes the operation contract and evidence requirements;
- `spec.proposedAction` states that KubeActuary records but does not execute
  the proposed action;
- `spec.evidence` describes embedded collector/reviewer evidence summaries;
- `spec.rollback` describes explicit rollback evidence;
- `status` describes gate state, digest, and evidence gaps;
- `status.conditions` describes Kubernetes-style condition mapping.

## Fields Covered

The offline check requires descriptions for:

- `spec`
- `spec.intent`
- `spec.actor`
- `spec.proposedAction`
- `spec.risk`
- `spec.requiredEvidence`
- `spec.evidence`
- `spec.postChecks`
- `spec.rollback`
- `status`
- `status.phase`
- `status.gate`
- `status.digest`
- `status.conditions`
