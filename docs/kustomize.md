# Kustomize

KubeActuary includes a Kustomize base and two controller RBAC overlays.

## Layout

```text
deploy/kustomize/base
deploy/kustomize/overlays/controller-namespace
deploy/kustomize/overlays/controller-cluster
```

The base contains only the `OperationCapsule` CRD. Controller RBAC remains
optional and is added only through an overlay.

## Build

```sh
kubectl kustomize deploy/kustomize/base
kubectl kustomize deploy/kustomize/overlays/controller-namespace
kubectl kustomize deploy/kustomize/overlays/controller-cluster
```

The namespace overlay renders a `Role` and `RoleBinding`. The cluster overlay
renders a `ClusterRole` and `ClusterRoleBinding`.

## Safety Boundary

The overlays include only:

- `Namespace`
- `ServiceAccount`
- `Role` or `ClusterRole`
- `RoleBinding` or `ClusterRoleBinding`
- `CustomResourceDefinition`

They do not render a controller `Deployment`, workload mutations, admission
webhooks, or target workload resources.

## Verification

```sh
python3 -B scripts/verify_kustomize.py
```

This verifier checks that copied CRD/RBAC manifests match the canonical
`deploy/` files, runs `kubectl kustomize` for the base and overlays, and checks
that the rendered RBAC remains scoped to OperationCapsule read/watch and status
patch permissions.
