# Agent Codex Workflow Runbook

Purpose: let Codex or another coding agent use KubeActuary as an auditable
planning and gate layer while keeping cluster writes outside the agent tool set.

Safety boundary:

- use only `bin/kube-actuary` commands that record, collect, verify, or gate
  evidence;
- never run the proposed Kubernetes write command from the capsule;
- attach external evidence explicitly before relying on `gate`.

Local smoke:

```sh
python3 -B bin/kube-actuary help agents --format json
python3 -B bin/kube-actuary validate examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary verify examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary gate examples/apply-configmap.preflight.capsule.json
```

Agent workflow:

1. Read `kube-actuary help agents --format json`.
2. Draft an operation capsule from the proposed command or manifest path.
3. Inspect risk, target, and required evidence.
4. Collect or attach evidence using local-only commands.
5. Run verify and gate.
6. Hand the capsule and gate output to the external executor or reviewer.
