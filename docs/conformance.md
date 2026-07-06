# Conformance Suite

The local conformance suite freezes the upstream Kubernetes N/N-1/N-2 matrix
used by the KubeActuary alpha contract.

Source:

- https://kubernetes.io/releases/version-skew-policy/

Source snapshot: 2026-07-06.

Supported upstream minors:

| Track | Minor |
| --- | --- |
| N | `1.36` |
| N-1 | `1.35` |
| N-2 | `1.34` |

Local conformance checks:

- `scripts/verify_crd_compatibility.py`;
- `scripts/verify_crd_upgrade_fixtures.py`;
- `scripts/verify_crd_explain_quality.py`;
- YAML parse coverage for CRD, RBAC, Kustomize, Helm, admission, and examples.

Verification:

```sh
python3 -B scripts/verify_conformance_suite.py
```

This verifier is offline and does not start Kubernetes clusters. Live cluster
matrix work remains separate from this local conformance seed.
