# Interoperability Contract

KubeActuary is intended to sit between AI tools and Kubernetes execution paths.
It should be useful even when the AI tool is replaced.

## CLI Contract

An agent can create a capsule:

```sh
kube-actuary draft --intent "$INTENT" --command "$KUBECTL_COMMAND" --out op.json
```

A collector can attach evidence:

```sh
kube-actuary attach-evidence op.json \
  --id server-dry-run \
  --summary "kubectl apply --dry-run=server succeeded" \
  --source dry-run.log \
  --out op.with-dry-run.json
```

A built-in collector can attach auth evidence:

```sh
kube-actuary collect auth op.json --out op.with-auth.json
```

A runner can gate execution:

```sh
kube-actuary gate op.with-all-evidence.json
```

Only `gate: open` is an execution candidate. KubeActuary v0 does not execute the
candidate command.

## MCP Tool Contract

A future MCP server should expose these tools:

| Tool | Purpose | Writes cluster |
| --- | --- | --- |
| `draft_operation_capsule` | Create a capsule from intent plus command or manifest | No |
| `inspect_operation_capsule` | Summarize target, risk, evidence, and state | No |
| `attach_operation_evidence` | Attach an evidence record to a capsule | No |
| `verify_operation_capsule` | Check required evidence | No |
| `gate_operation_capsule` | Return open/closed execution decision | No |
| `execute_approved_capsule` | Execute only a verified capsule | Yes, future only |

The first five tools are safe for local development because they operate on
capsule files rather than live cluster state.

## GitOps Contract

For GitOps systems, a pull request can include:

- the manifest change,
- the generated capsule,
- evidence logs from CI,
- a gate result.

The GitOps reconciler remains the execution engine. KubeActuary supplies the
change evidence and audit trail.

## Admission Contract

A future admission controller can require mutation requests from known AI
identities to include:

- `kubeactuary.dev/capsule-id`,
- `kubeactuary.dev/capsule-digest`,
- `kubeactuary.dev/gate=open`.

This makes AI-originated changes distinguishable without requiring every cluster
to run a new agent framework.
