# Policy Adapters

Policy adapters convert external tool output into KubeActuary evidence. They do
not replace the gate and do not execute proposed Kubernetes writes.

## Kyverno

```sh
python3 -B scripts/adapt_kyverno_evidence.py kyverno-output.json
```

The adapter reads captured Kyverno CLI JSON and emits `kyverno-policy` evidence.
It does not run Kyverno, contact a cluster, or mutate resources.

Evidence rules:

- any `fail` or `error` result makes evidence `ok: false`;
- `pass`, `warn`, and `skip` are counted in `policyResults`;
- output includes a stable `reason` of `policy-pass` or `policy-fail`.

## Verification

```sh
python3 -B scripts/verify_kyverno_adapter.py
```

The verifier uses pass/fail fixtures under `tests/fixtures/kyverno`.

## OPA/Rego

```sh
python3 -B scripts/adapt_opa_evidence.py opa-eval-output.json
```

The adapter reads captured `opa eval --format=json` output and emits
`opa-rego-policy` evidence. It does not run OPA, contact a cluster, or mutate
resources.

Evidence rules:

- empty deny/violation results make evidence `ok: true`;
- non-empty deny/violation results make evidence `ok: false`;
- output includes a stable `reason` of `policy-pass` or `policy-fail`.

Verification:

```sh
python3 -B scripts/verify_opa_adapter.py
```

The verifier uses pass/fail fixtures under `tests/fixtures/opa`.
