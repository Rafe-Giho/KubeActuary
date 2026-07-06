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

## kube-linter

```sh
python3 -B scripts/adapt_kube_linter_evidence.py kube-linter-output.json
```

The adapter reads captured kube-linter JSON output and emits
`kube-linter-policy` evidence. It does not run kube-linter, contact a cluster,
or mutate resources.

Evidence rules:

- zero reports make evidence `ok: true`;
- one or more reports make evidence `ok: false`;
- output counts error, warning, and info severities.

Verification:

```sh
python3 -B scripts/verify_kube_linter_adapter.py
```

The verifier uses pass/fail fixtures under `tests/fixtures/kube-linter`.

## kube-score

```sh
python3 -B scripts/adapt_kube_score_evidence.py kube-score-output.json
```

The adapter reads captured `kube-score score -o json` output and emits
`kube-score-policy` evidence. It does not run kube-score, contact a cluster,
or mutate resources.

Evidence rules:

- `CRITICAL` or numeric grade `1` makes evidence `ok: false`;
- `WARNING` or numeric grade `5` makes evidence `ok: false`;
- `OK`, `ALMOST_OK`, numeric grades `7` and `10`, and skipped checks are
  counted without failing evidence;
- unknown grades fail closed as `policy-fail`.

Verification:

```sh
python3 -B scripts/verify_kube_score_adapter.py
```

The verifier uses pass/fail fixtures under `tests/fixtures/kube-score`.

## Pluto

```sh
python3 -B scripts/adapt_pluto_evidence.py pluto-output.json
```

The adapter reads captured `pluto detect-* -o json` output and emits
`pluto-deprecated-api` evidence. It does not run Pluto, contact a cluster, or
mutate resources.

Evidence rules:

- zero `items` make evidence `ok: true`;
- one or more deprecated or removed API findings make evidence `ok: false`;
- removed APIs, deprecated APIs, unavailable replacements, and target versions
  are counted in `deprecatedApiResults`.

Verification:

```sh
python3 -B scripts/verify_pluto_adapter.py
```

The verifier uses pass/fail fixtures under `tests/fixtures/pluto`.
