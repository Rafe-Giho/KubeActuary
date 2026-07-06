# MCP Integration

KubeActuary exposes a safe stdlib JSON-RPC/MCP wrapper for local agent
workflows. It does not expose raw Kubernetes write execution.

## Client Config

Example config:

```json
{
  "mcpServers": {
    "kube-actuary": {
      "command": "python3",
      "args": [
        "-B",
        "scripts/kube_actuary_mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

The same config is available at:

```text
examples/mcp-client-config.json
```

Run MCP clients from the repository root or adjust the script path to an
absolute path.

## Safe Tools

- `draft_operation_capsule`
- `inspect_operation_capsule`
- `attach_operation_evidence`
- `verify_operation_capsule`
- `gate_operation_capsule`

`execute_approved_capsule` remains disabled. The wrapper never runs
`kubectl apply`, `kubectl delete`, or proposed Kubernetes write commands.

## Verification

```sh
python3 -B scripts/verify_mcp_contract.py
python3 -B scripts/verify_mcp_docs.py
```

Expected:

```text
mcp-contract: passed
mcp-docs: passed
```
