# Agent Integration

KubeActuary v0.9.5 exposes an agent-readable CLI contract. A packaged MCP
server is not part of the public v0.9.5 artifact.

Current integration point:

```sh
python3 -B bin/kube-actuary help agents --format json
```

That JSON describes commands, expected exit codes, cluster access, capsule
writes, and the no-write safety boundary. Agents should use it to decide which
CLI commands are safe to call.

## Safe Current Flow

1. Draft a capsule with `draft`.
2. Inspect or validate the capsule.
3. Collect evidence with `collect auth`, `collect dry-run`, `collect diff`,
   `collect rollback`, or `collect health-plan`.
4. Attach external evidence explicitly when required.
5. Run `verify` and `gate`.
6. Hand an open-gate capsule to a human, CI, GitOps, or a future bounded
   executor.

The CLI does not execute the proposed Kubernetes write command.

## Future MCP Boundary

A future MCP wrapper should expose only the same evidence and gate operations:

- draft operation capsule;
- inspect operation capsule;
- attach operation evidence;
- verify operation capsule;
- gate operation capsule.

Direct execution of approved capsules must remain disabled until the gate,
audit, and live-evidence story is proven.
