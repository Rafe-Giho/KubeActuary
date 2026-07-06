# KubeActuary Release Checklist

Use this checklist before publishing an alpha release. The default release path
is local-first and does not require a Kubernetes cluster.

## Preflight

- [ ] `VERSION` matches the intended release.
- [ ] `CHANGELOG.md` has a section for the release version.
- [ ] `docs/release-taskboard.md` marks the release-scope tasks as `DONE` or
      explicitly leaves them out of scope.
- [ ] README and README.ko describe the public CLI surface.
- [ ] Safety boundaries still state that proposed Kubernetes writes are not
      executed by default.

## Local Verification

Run:

```sh
python3 -B scripts/verify_release.py --version current
python3 -B -m unittest discover -s tests
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
python3 -B scripts/generate_release_notes.py --version "$(cat VERSION)" --output -
git diff --check
```

Expected:

- release verification passes;
- unit tests pass;
- release notes render without errors;
- CRD upgrade and rollback fixtures verify offline;
- CRD explain descriptions and example commands verify offline;
- controller contract emits status-only patch examples and OperationCapsule-only
  watch commands;
- controller RBAC grants only OperationCapsule read/watch and status patch
  permissions;
- controller runtime contract emits health, readiness, metrics, and Lease
  configuration without contacting the cluster;
- controller resource budget contract and measurement parser verify offline;
- lightweight cluster smoke plan verifies offline;
- Helm chart contract verifies offline;
- Kustomize base and overlays render with `kubectl kustomize`;
- release archives verify SHA-256 sidecars and install smoke;
- no whitespace errors;
- no `__pycache__` directories remain.

## Artifact Checks

- [ ] CLI version prints the intended version.
- [ ] `kube-actuary help agents --format json` parses.
- [ ] Agent help JSON includes the expected `schemaVersion` and
      `compatibility.requiredCommandFields`.
- [ ] CRD YAML parses.
- [ ] `kubectl explain` runbook is reviewed for the current CRD.
- [ ] CRD rollback fixture YAML parses.
- [ ] controller dry-run contract check passes.
- [ ] controller RBAC check passes.
- [ ] controller runtime contract check passes.
- [ ] controller resource budget check passes.
- [ ] lightweight cluster smoke plan check passes.
- [ ] live kind/minikube/MicroK8s/k3s evidence is attached before claiming
      matrix support.
- [ ] Helm chart check passes; run `helm template` when Helm is available.
- [ ] Kustomize base and overlays render.
- [ ] release archive checksum and install smoke pass.
- [ ] example capsules validate and gate as expected.
- [ ] generated release notes include verification and rollback notes.

## Publish Gate

- [ ] GitHub Actions CI is green on the release branch or PR.
- [ ] Release notes are reviewed.
- [ ] Tag name matches `v<VERSION>`.
- [ ] Published artifacts include source, CLI/plugin files, CRD seed, docs, and
      example capsules.

## Rollback

- [ ] Keep the previous tag available.
- [ ] If publishing fails, delete the draft release and rerun local
      verification before retrying.
- [ ] No cluster rollback is required for the local CLI-only alpha path.
