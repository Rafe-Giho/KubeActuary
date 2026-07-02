# Evidence Collectors

Collectors attach evidence to an `OperationCapsule` without executing the
proposed Kubernetes write.

## Implemented: `collect auth`

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

## Safety Boundary

Collectors must not execute the proposed cluster mutation. They may run
read-only checks, dry-run checks, or local file/hash checks.

The current collector runs only:

```text
kubectl auth can-i ...
```

It does not run `kubectl apply`, `kubectl scale`, `kubectl delete`, or any other
proposed operation.

## Planned Collectors

- `collect diff`: attach `kubectl diff` output.
- `collect dry-run`: attach server-side dry-run result.
- `collect rollback`: attach rollback command or manifest snapshot.
- `collect health-plan`: attach post-change verification plan.

