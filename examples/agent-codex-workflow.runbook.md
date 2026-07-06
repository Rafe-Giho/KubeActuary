# Agent Codex Workflow Runbook

Purpose: let Codex or another coding agent use KubeActuary as an auditable
planning and gate layer while keeping cluster writes outside the agent tool set.

Safety boundary:

- call only the safe MCP tools exposed by `scripts/kube_actuary_mcp_server.py`;
- keep `execute_approved_capsule` disabled;
- attach external evidence explicitly before relying on `gate`.

Safe MCP tools:

- `draft_operation_capsule`
- `inspect_operation_capsule`
- `attach_operation_evidence`
- `verify_operation_capsule`
- `gate_operation_capsule`

Local smoke:

```sh
python3 -B scripts/verify_mcp_contract.py
python3 -B scripts/verify_agent_help_contract.py
python3 -B scripts/verify_release.py --version 0.2.0
```

Agent workflow:

1. Read `kube-actuary help agents --format json`.
2. Draft an operation capsule from the proposed command or manifest path.
3. Inspect risk, target, and required evidence.
4. Collect or attach evidence using local-only commands.
5. Run verify and gate.
6. Hand the capsule and gate output to the external executor or reviewer.
