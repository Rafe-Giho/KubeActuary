# v0.2.0 Test Plan

Run these checks before tagging v0.2.0.

## Automated

```sh
python3 -B scripts/verify_release.py --version 0.2.0
python3 -B -m unittest discover -s tests
```

Expected:

- release verification suite passes;
- all tests pass;
- collector tests cover auth, dry-run, diff, rollback, health-plan, digest,
  validate, doctor, normalized collector failures, human help, agent JSON help,
  structured help compatibility, controller dry-run contract, and full manifest
  gate behavior;
- no `__pycache__` directories are left behind when using `-B`.

## CLI Smoke Tests

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
python3 -B bin/kube-actuary help
python3 -B bin/kube-actuary help safety
python3 -B bin/kube-actuary help agents --format json
python3 -B bin/kube-actuary digest examples/apply-configmap.preflight.capsule.json
python3 -B scripts/verify_crd_compatibility.py
python3 -B scripts/verify_crd_explain_quality.py
python3 -B scripts/verify_crd_upgrade_fixtures.py
python3 -B scripts/verify_controller_contract.py
python3 -B scripts/generate_release_notes.py --version 0.2.0 --output -
python3 -B bin/kube-actuary render-crd examples/apply-configmap.preflight.capsule.json --name apply-configmap --namespace default
python3 -B bin/kube-actuary gate examples/apply-configmap.preflight.capsule.json
python3 -B bin/kube-actuary gate examples/scale-prod-deployment.capsule.json
```

Expected:

- version prints `kube-actuary 0.2.0`;
- help includes the v0.2 collectors, `validate`, and `digest`;
- validate prints `validation: passed` for the included preflight capsule;
- doctor prints local runtime checks and warns, without failing, when kubectl is
  absent;
- release notes dry-run prints verification and rollback sections;
- CRD upgrade fixture check prints `crd-upgrade-fixtures: passed`;
- controller contract check prints `controller-contract: passed`;
- `help` output includes `USAGE`, command groups, help topics, examples, and
  the safety model;
- `help agents --format json` parses as JSON and exposes command safety,
  allowed cluster access, evidence ids, stable exit-code meanings,
  `schemaVersion`, and compatibility fields;
- digest prints `sha256:<hex>`;
- rendered CRD includes `kubeactuary.dev/capsule-digest`;
- verified manifest preflight example opens the gate;
- high-risk draft example keeps the gate closed.

## Format Checks

```sh
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/scale-prod-deployment.capsule.json
python3 -B -m json.tool examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool examples/apply-configmap.diff.capsule.json
python3 -B -m json.tool examples/apply-configmap.rollback.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml examples/operationcapsule-scale.yaml examples/configmap-demo.yaml examples/configmap-demo.rollback.yaml
```

Expected:

- JSON examples parse;
- schema JSON parses;
- GitHub Actions workflow, CRD YAML, CRD rollback fixture YAML, and example YAML
  files parse.

## Safety Checks

Confirm from code and tests:

- `collect auth` runs only `kubectl auth can-i`;
- `collect dry-run` runs only `kubectl apply --dry-run=server -f <manifest>`;
- `collect diff` runs only `kubectl diff -f <manifest>`;
- dry-run and diff collectors attach failed `inapplicable` evidence instead of
  executing imperative proposed commands when no manifest is available;
- `doctor` runs only `kubectl version --client=true -o json`;
- collector failure summaries use stable prefixes and `reason` fields for
  inapplicable, missing-source, and command-failed evidence;
- rendered CRD evidence preserves collector `reason` fields;
- rendered CRD status preserves phase, gate, digest, missing/failed evidence,
  and condition mappings;
- offline CRD compatibility smoke checks upstream N/N-1/N-2 and managed-source
  notes;
- offline CRD upgrade fixture check verifies the current CRD, rollback fixture,
  and runbook identity;
- offline kubectl explain quality check verifies OpenAPI descriptions and
  explain commands;
- controller reconcile helper emits status-only patches and watches only
  `operationcapsules.ops.kubeactuary.dev`;
- `collect rollback`, `collect health-plan`, `validate`, and `digest` do not
  call `kubectl`;
- failed required evidence closes the gate.

## Local Taskboard

```sh
python3 -B scripts/verify_release.py --list
```

Expected:

- `0.2.0` and `current` suites are available;
- suite checks cover unit tests, CLI help, agent JSON help, validate, doctor,
  release notes dry-run, CRD compatibility smoke, CRD explain quality, CRD
  upgrade fixtures, controller contract, digest, CRD render, gate behavior,
  JSON/YAML parsing, and `git diff --check`.
