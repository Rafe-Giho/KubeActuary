# v0.2.0 Test Results

Run date: 2026-07-06.

## Summary

Result: passed for the v0.2.0 alpha target.

## Commands Run

### Unit Tests

```sh
python3 -B scripts/verify_release.py --version 0.2.0
python3 -B -m unittest discover -s tests
```

Result:

```text
verification: passed (21 checks)
Ran 44 tests
OK
```

Coverage included:

- local release verification suite;
- `collect auth`;
- `collect dry-run`;
- `collect diff` exit codes `0`, `1`, and `2`;
- inapplicable dry-run/diff without a manifest;
- rollback command and manifest evidence;
- health-plan evidence;
- validate valid capsule, invalid capsule, and JSON output behavior;
- doctor missing-kubectl warning, fake kubectl version parsing, and JSON skew
  warning behavior;
- normalized collector failure summaries for inapplicable, missing-source, and
  command-failed evidence;
- CRD rendering preserves collector `reason` fields;
- CRD status rendering maps phase, gate, missing/failed evidence, digest, and
  conditions;
- CRD schema freezes v0.3.0 spec, embedded evidence, rollback, and status fields;
- offline CRD compatibility smoke checks upstream Kubernetes `1.36`, `1.35`,
  `1.34` and managed-service source links;
- offline CRD upgrade fixture check validates the current CRD, rollback fixture,
  and runbook identity;
- offline kubectl explain quality check validates OpenAPI descriptions and live
  explain command examples;
- pure controller reconcile model computes status-only patches;
- controller watch contract stays scoped to OperationCapsule resources;
- controller RBAC grants OperationCapsule read/watch and status-only write
  permissions;
- GitHub Actions workflow YAML parsing;
- release notes dry-run generation;
- digest stability across status evidence changes;
- human help sections;
- safety help execution boundary;
- agent-readable JSON help contract;
- versioned structured help compatibility fields;
- full manifest evidence flow opening the gate.

### CLI Version and Help

```sh
python3 -B bin/kube-actuary --version
python3 -B bin/kube-actuary --help
python3 -B bin/kube-actuary collect --help
python3 -B bin/kube-actuary collect dry-run --help
python3 -B bin/kube-actuary collect diff --help
python3 -B bin/kube-actuary collect rollback --help
python3 -B bin/kube-actuary collect health-plan --help
python3 -B bin/kube-actuary validate examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary doctor --kubectl /definitely/missing/kubectl
python3 -B scripts/generate_release_notes.py --version 0.2.0 --output -
python3 -B scripts/verify_crd_compatibility.py
python3 -B scripts/verify_crd_explain_quality.py
python3 -B scripts/verify_crd_upgrade_fixtures.py
python3 -B scripts/verify_controller_contract.py
python3 -B scripts/verify_controller_rbac.py
python3 -B bin/kube-actuary help
python3 -B bin/kube-actuary help workflow
python3 -B bin/kube-actuary help safety
python3 -B bin/kube-actuary help commands
python3 -B bin/kube-actuary help agents --format json
```

Result:

- version prints `kube-actuary 0.2.0`;
- top-level help lists `digest` and `help`;
- `validate` prints `validation: passed` for the included preflight capsule;
- `doctor` prints `doctor: ok-with-warnings` when kubectl is missing;
- release notes dry-run prints verification and rollback sections;
- CRD compatibility smoke prints `crd-compatibility: passed`;
- CRD explain quality check prints `crd-explain-quality: passed`;
- CRD upgrade fixture check prints `crd-upgrade-fixtures: passed`;
- controller contract check prints `controller-contract: passed`;
- controller RBAC check prints `controller-rbac: passed`;
- collect help lists `auth`, `dry-run`, `diff`, `rollback`, and `health-plan`;
- `help` output includes `USAGE`, `CORE COMMANDS`, `COLLECTOR COMMANDS`,
  `HELP TOPICS`, examples, and `SAFETY MODEL`;
- `help workflow`, `help safety`, and `help commands` print topic-specific
  human-readable guidance;
- `help agents --format json` prints parseable JSON with command safety,
  allowed cluster access, evidence ids, stable exit-code meanings,
  `schemaVersion`, and compatibility fields;
- each v0.2 collector help command exits successfully.

### Digest, Render, and Gate

```sh
python3 -B bin/kube-actuary digest examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary render-crd examples/apply-configmap.preflight.capsule.json --name apply-configmap --namespace default --out /private/tmp/kubeactuary-render-v020.yaml
python3 -B bin/kube-actuary gate examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary gate examples/scale-prod-deployment.capsule.json
```

Result:

- digest printed `sha256:fdd50fd8d5baed65c00640cedabc0b41f3466be51825ed094131d833ea046ee7`;
- rendered CRD includes `kubeactuary.dev/capsule-digest`;
- rendered CRD includes `postChecks`, collector summaries, `diffFound`,
  rollback `manifestSha256`, `status.phase`, `status.gate`, `status.digest`,
  and conditions;
- manifest preflight example opened the gate;
- high-risk production scale draft kept the gate closed because evidence is
  missing.

### JSON and YAML Parsing

```sh
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/scale-prod-deployment.capsule.json
python3 -B -m json.tool examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool examples/apply-configmap.diff.capsule.json
python3 -B -m json.tool examples/apply-configmap.rollback.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml examples/operationcapsule-scale.yaml examples/configmap-demo.yaml examples/configmap-demo.rollback.yaml /private/tmp/kubeactuary-render-v020.yaml
```

Result:

- example capsule JSON files parse;
- schema JSON parses;
- GitHub Actions workflow, CRD YAML, rollback fixture YAML, controller RBAC
  YAML, CR example YAML, manifest examples, and generated CRD object YAML parse.

### Cache Check

```sh
find . -name __pycache__ -type d -print
```

Result:

- no `__pycache__` directories found.

## Release Judgment

v0.2.0 is suitable as a local-first evidence collector alpha release.

It is not production-ready as a live controller or admission system. The current
controller work is an offline status reconcile contract, not a deployed
controller.
