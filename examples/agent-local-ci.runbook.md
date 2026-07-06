# Agent Local CI Runbook

Purpose: let a CI agent produce and verify KubeActuary evidence without direct
cluster write execution.

Safety boundary:

- do not run proposed Kubernetes write commands;
- use `draft`, `validate`, `verify`, and `gate` as local evidence checks;
- use collector output as evidence, not as an execution approval by itself.

Example CI steps:

```sh
python3 -B bin/kube-actuary help agents --format json
python3 -B scripts/verify_agent_help_contract.py
python3 -B bin/kube-actuary validate examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary verify examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary gate examples/apply-configmap.preflight.capsule.json
```

Optional MCP contract check:

```sh
python3 -B scripts/verify_mcp_contract.py
```

The CI job should publish the capsule JSON and command output as artifacts. A
separate human or GitOps system remains responsible for applying manifests.
