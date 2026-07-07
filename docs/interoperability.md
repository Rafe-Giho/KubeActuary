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

## Agent-Readable CLI Contract

The public v0.9.5 integration surface is the CLI help contract:

```sh
python3 -B bin/kube-actuary help agents --format json
```

It describes safe commands, expected exit codes, cluster access, and the
commands that never execute the proposed Kubernetes write. A future MCP wrapper
should preserve this same boundary instead of introducing direct cluster-write
execution.

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
