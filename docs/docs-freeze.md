# Documentation Freeze

The v0.9.3 documentation freeze checks that public release-candidate docs and
examples are present, parseable where applicable, and consistent with the
KubeActuary safety model.

## Gate

Run:

```sh
python3 -B scripts/verify_docs_freeze.py
```

Expected:

```text
docs-freeze: passed
public-examples: 10 checked
writes: disabled
```

This is a public examples audit. It is local-only and does not contact the cluster.

## Checklist

- README and README.ko are present.
- SECURITY, threat model, API freeze, release checklist, and taskboard are
  present.
- Public capsule JSON examples parse and keep the `OperationCapsule` shape.
- Public YAML examples include `apiVersion` and `kind`.
- Agent runbooks keep direct Kubernetes writes outside the agent workflow.
- Release verification includes this gate before tagging.
