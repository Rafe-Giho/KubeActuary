# Kubernetes Compatibility

Source snapshot: 2026-07-06.

This document records the compatibility target for the CRD alpha line. Provider
support windows change over time, so refresh the source links before cutting a
public release.

## Upstream Kubernetes

Source: https://kubernetes.io/releases/version-skew-policy/

The Kubernetes project currently maintains release branches for the most recent
three minor releases:

- `1.36`
- `1.35`
- `1.34`

KubeActuary v0.3.x uses those versions as the upstream CRD validation target:

| Track | Minor |
| --- | --- |
| N | `1.36` |
| N-1 | `1.35` |
| N-2 | `1.34` |

The CRD uses `apiextensions.k8s.io/v1`, a namespaced resource, and `status`
subresource support. It avoids conversion webhooks and admission dependencies
in the alpha contract.

## Managed Kubernetes

### Amazon EKS

Source: https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html

As of this snapshot:

- standard support: `1.36`, `1.35`, `1.34`, `1.33`
- extended support: `1.32`, `1.31`, `1.30`

EKS standard support runs for 14 months after an EKS version release, then
extended support runs for 12 months.

### Google Kubernetes Engine

Source: https://cloud.google.com/kubernetes-engine/docs/release-schedule

GKE support depends on release channel enrollment. The release schedule lists
minor-version availability, auto-upgrade timing, end of standard support, and
end of extended support. Dates are best-effort predictions and should be
refreshed before a public release.

As of this snapshot, GKE lists `1.36` in the release schedule, and versions
`1.29` and earlier are out of support.

### Azure Kubernetes Service

Source: https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions

As of this snapshot:

- GA table includes `1.32`, `1.33`, `1.34`, `1.35`, `1.36`, and projected `1.37`
- AKS follows a 12-month support policy for GA Kubernetes versions
- LTS requires explicit enablement

## Local Validation Scope

The local v0.3.1 smoke check verifies:

- CRD API version is `apiextensions.k8s.io/v1`
- CRD version is `v1alpha1`
- resource is namespaced
- status subresource is enabled
- frozen v0.3 fields are present
- condition types are present
- this compatibility document contains current source links and upstream
  N/N-1/N-2 minors

Live kind/minikube validation remains a follow-up matrix check because it
requires Kubernetes binaries and cluster startup outside the current stdlib-only
CLI path.
