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
  structured help compatibility, controller dry-run contract, controller RBAC,
  controller runtime contract, controller resource budget, lightweight cluster
  smoke harness, Helm chart contract, Kustomize rendering, release archives, and
  Krew manifest generation, SBOM/provenance generation, air-gapped manifest
  generation, Kyverno adapter fixtures, OPA adapter fixtures, kube-linter
  adapter fixtures, kube-score adapter fixtures, Pluto adapter fixtures, and
  adapter contract severity normalization, and full manifest gate behavior;
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
python3 -B scripts/verify_controller_rbac.py
python3 -B scripts/verify_controller_runtime_contract.py
python3 -B scripts/verify_controller_resource_budget.py
python3 -B scripts/verify_lightweight_cluster_smoke.py
python3 -B scripts/verify_helm_chart.py
python3 -B scripts/verify_kustomize.py
python3 -B scripts/verify_release_archives.py
python3 -B scripts/verify_krew_manifest.py
python3 -B scripts/verify_supply_chain.py
python3 -B scripts/verify_airgap_bundle.py
python3 -B scripts/verify_kyverno_adapter.py
python3 -B scripts/verify_opa_adapter.py
python3 -B scripts/verify_kube_linter_adapter.py
python3 -B scripts/verify_kube_score_adapter.py
python3 -B scripts/verify_pluto_adapter.py
python3 -B scripts/verify_adapter_contract.py
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
- controller RBAC check prints `controller-rbac: passed`;
- controller runtime check prints `controller-runtime: passed`;
- controller resource budget check prints `controller-resource-budget: passed`;
- lightweight cluster smoke check prints `lightweight-cluster-smoke: passed`;
- Helm chart check prints `helm-chart: passed`;
- Kustomize check prints `kustomize: passed`;
- release archive check prints `release-archives: passed`;
- Krew manifest check prints `krew-manifest: passed`;
- supply-chain check prints `supply-chain: passed`;
- airgap bundle check prints `airgap-bundle: passed`;
- Kyverno adapter check prints `kyverno-adapter: passed`;
- OPA adapter check prints `opa-adapter: passed`;
- kube-linter adapter check prints `kube-linter-adapter: passed`;
- kube-score adapter check prints `kube-score-adapter: passed`;
- Pluto adapter check prints `pluto-adapter: passed`;
- adapter contract check prints `adapter-contract: passed`;
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
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml charts/kubeactuary/Chart.yaml charts/kubeactuary/values.yaml deploy/kustomize/base/kustomization.yaml deploy/kustomize/overlays/controller-namespace/kustomization.yaml deploy/kustomize/overlays/controller-cluster/kustomization.yaml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml examples/operationcapsule-scale.yaml examples/configmap-demo.yaml examples/configmap-demo.rollback.yaml
```

Expected:

- JSON examples parse;
- schema JSON parses;
- GitHub Actions workflow, Helm chart metadata, Kustomize manifests, CRD YAML,
  CRD rollback fixture YAML, controller RBAC YAML, and example YAML files parse.

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
- controller RBAC grants only OperationCapsule read/watch and status patch
  permissions;
- controller runtime helper emits health, readiness, metrics, and
  leader-election Lease configuration without contacting the cluster;
- controller resource budget helper sets idle <50m CPU and <64Mi memory targets
  and parses `kubectl top` samples;
- lightweight cluster smoke helper uses server-side dry-run plans and covers
  kind, minikube, MicroK8s, and k3s without default writes;
- Helm chart packages the CRD under `crds/` and keeps optional controller RBAC
  disabled by default;
- Kustomize base renders only the CRD, while controller overlays add only
  optional RBAC;
- release archive generator emits multi-target archives, SHA-256 sidecars, and
  install smoke for CLI/plugin/controller;
- Krew manifest generator maps `kubectl-actuary` and adjacent `kube-actuary`
  helper for each archive target;
- SBOM/provenance generator records file hashes and release archive subjects;
- air-gapped manifest generator lists required release and repository artifacts
  with SHA-256 digests;
- Kyverno adapter converts captured CLI JSON to `kyverno-policy` evidence and
  fails on policy failures;
- OPA adapter converts captured `opa eval --format=json` output to
  `opa-rego-policy` evidence and fails on policy violations;
- kube-linter adapter converts captured JSON output to `kube-linter-policy`
  evidence and fails on linter reports;
- kube-score adapter converts captured JSON output to `kube-score-policy`
  evidence and fails on critical, warning, or unknown grades;
- Pluto adapter converts captured JSON output to `pluto-deprecated-api`
  evidence and fails on deprecated or removed API findings;
- adapter contract verification requires common evidence fields and normalized
  `severity` values across pass/fail fixtures;
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
  upgrade fixtures, controller contract, controller RBAC, controller runtime,
  controller resource budget, lightweight cluster smoke, digest, CRD render,
  Helm chart, Kustomize, release archives, Krew manifest, supply chain,
  air-gapped bundle, Kyverno adapter, OPA adapter, kube-linter adapter,
  kube-score adapter, Pluto adapter, adapter contract, gate behavior, JSON/YAML
  parsing, and `git diff --check`.
