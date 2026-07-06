# CRD Upgrade And Rollback Fixtures

This document records the v0.3.2 CRD fixture path for local review and future
cluster smoke tests.

## Files

- current CRD: `deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml`
- rollback fixture: `deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml`

The fixture keeps the same CRD identity:

- `metadata.name: operationcapsules.ops.kubeactuary.dev`
- `spec.group: ops.kubeactuary.dev`
- `spec.scope: Namespaced`
- `spec.versions[0].name: v1alpha1`

## Offline Verification

```sh
python3 -B scripts/verify_crd_upgrade_fixtures.py
```

Expected:

```text
crd-upgrade-fixtures: passed
```

## Server Dry-Run Sequence

Run this against a disposable cluster before a public CRD release:

```sh
kubectl apply --server-side --dry-run=server \
  -f deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml

kubectl apply --server-side --dry-run=server \
  -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml

kubectl apply --server-side --dry-run=server \
  -f deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml
```

The first command validates the rollback fixture. The second validates the
upgrade path to the current CRD. The third validates the rollback manifest.

## Live Apply Sequence

Use only in a disposable cluster:

```sh
kubectl apply --server-side \
  -f deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml

kubectl apply --server-side \
  -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml

kubectl apply --server-side \
  -f deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml
```

Do not run the live apply sequence against a shared cluster without first
reviewing stored `OperationCapsule` objects. CRD schema rollback can reject
newer fields on subsequent writes.

## Current Limit

The local v0.3.2 verification is offline. It proves fixture identity and schema
shape, but it does not replace a real kind or minikube apply test.
