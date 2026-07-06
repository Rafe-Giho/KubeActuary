# API Freeze

The v0.9.2 API freeze records the public local capsule schema and
`OperationCapsule` CRD contract before release-candidate work.

The compatibility rule is additive-only. Existing required fields, published
API identity, accepted enum values, and evidence/status fields must remain
available. New optional fields and descriptions are allowed.

## Gate

Run:

```sh
python3 -B scripts/verify_api_freeze.py
```

Expected:

```text
api-freeze: passed
policy: additive-only
breaking-schema-diff: guarded
```

The verifier compares the current JSON Schema and CRD against
`schemas/api-freeze.v0.9.2.json`. It is an offline no breaking schema diff gate
and does not contact the cluster.

## Breaking Changes

Treat these as breaking before v1.0.0:

- removing or renaming a frozen JSON Schema field;
- changing `kubeactuary.dev/v0alpha1` or `OperationCapsule`;
- changing the CRD group, kind, version, or status subresource contract;
- removing accepted enum values for risk, scope, state, or status conditions;
- removing evidence fields used by collectors, adapters, admission, or audit.

If a breaking change is unavoidable, add a new versioned contract instead of
silently changing the frozen one.
