# Evidence Collectors

Collectors attach evidence to an `OperationCapsule` without executing the
proposed Kubernetes write.

## Implemented Collectors

### `collect auth`

`collect auth` derives a `kubectl auth can-i` check from the capsule target and
attaches the result as evidence.

For read-only capsules, it attaches:

- `read-auth`

For mutating capsules, it attaches:

- `write-auth`

Example:

```sh
python3 bin/kube-actuary collect auth capsule.json --out capsule.with-auth.json
```

The command stores:

- collector name,
- normalized reason,
- exact command argv,
- exit code,
- stdout,
- stderr,
- success boolean,
- timestamp,
- actor.

The collector considers the evidence successful only when:

- `kubectl auth can-i ...` exits with code `0`;
- the first stdout line is `yes`.

### `collect dry-run`

`collect dry-run` attaches `server-dry-run` evidence for manifest-based
operations.

Example:

```sh
python3 bin/kube-actuary collect dry-run capsule.json \
  --manifest manifest.yaml \
  --out capsule.with-dry-run.json
```

The collector runs only:

```text
kubectl apply --dry-run=server -f <manifest>
```

If no manifest path is available, it attaches failed `inapplicable` evidence
instead of running the proposed imperative command.

Missing manifest paths are reported as `missing-source` evidence. Failed
`kubectl apply --dry-run=server` commands are reported as `command-failed`
evidence.

### `collect diff`

`collect diff` attaches `diff` evidence for manifest-based operations.

Example:

```sh
python3 bin/kube-actuary collect diff capsule.json \
  --manifest manifest.yaml \
  --out capsule.with-diff.json
```

The collector runs only:

```text
kubectl diff -f <manifest>
```

Exit code `0` means no diff and is successful evidence. Exit code `1` means a
diff exists and is also successful evidence. Exit code `2` or higher is failed
evidence.

Diff summaries use stable prefixes: `command-ok`, `diff-found`, or
`command-failed`.

### `collect rollback`

`collect rollback` attaches explicit rollback evidence. It never guesses a
rollback plan.

Examples:

```sh
python3 bin/kube-actuary collect rollback capsule.json \
  --command "kubectl rollout undo deployment checkout-api -n prod"

python3 bin/kube-actuary collect rollback capsule.json \
  --manifest rollback.yaml
```

Manifest rollback evidence stores a SHA-256 hash of the rollback file.
Missing rollback manifests are reported as `missing-source` evidence.

### `collect health-plan`

`collect health-plan` attaches `post-checks` evidence from the capsule's
declared `spec.postChecks`. It records the plan only; it does not watch,
poll, or query live resources.

## Failure Summary Contract

Collector evidence uses stable `summary` prefixes and a matching `reason`
field:

| Prefix | Reason | Meaning |
| --- | --- | --- |
| `command-ok` | `command-ok` | A safe kubectl command succeeded. |
| `authorization-denied` | `authorization-denied` | `kubectl auth can-i` did not grant the requested action. |
| `diff-found` | `diff-found` | `kubectl diff` exited `1`, which is valid diff evidence. |
| `command-failed` | `command-failed` | A safe kubectl command returned a failing exit code. |
| `missing-source` | `manifest-not-found` | A declared manifest path was not readable. |
| `inapplicable` | `manifest-required` | A manifest-only collector was requested for an imperative command. |
| `rollback-command` | `rollback-command` | Explicit rollback command evidence was attached. |
| `rollback-manifest` | `rollback-manifest` | Explicit rollback manifest evidence was attached. |
| `health-plan` | `health-plan` | Declared post-change checks were attached. |

### `digest`

`digest` prints a deterministic SHA-256 digest over the capsule identity and
`spec`. It excludes `status.evidence`, so adding evidence does not change the
operation intent digest.

```sh
python3 bin/kube-actuary digest capsule.json
```

## Safety Boundary

Collectors must not execute the proposed cluster mutation. They may run
read-only checks, dry-run checks, or local file/hash checks.

The implemented collectors run only:

```text
kubectl auth can-i ...
kubectl apply --dry-run=server -f <manifest>
kubectl diff -f <manifest>
local file hashing
```

They do not run `kubectl scale`, `kubectl delete`, or any proposed imperative
write command.
