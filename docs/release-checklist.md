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
python3 -B scripts/verify_conformance_suite.py
python3 -B scripts/verify_release_taskboard.py
python3 -B scripts/verify_release_progress.py
python3 -B scripts/verify_version_worklist.py
python3 -B scripts/verify_external_gate_plan.py
python3 -B scripts/verify_external_gate_command_safety.py
python3 -B scripts/verify_external_gate_evidence.py
python3 -B scripts/verify_external_evidence_builder.py
python3 -B scripts/verify_external_evidence_bundle.py
python3 -B scripts/verify_release_evidence_directory.py
python3 -B scripts/verify_release_evidence_status.py
python3 -B scripts/verify_clean_artifacts.py
python3 -B scripts/verify_crd_upgrade_fixtures.py
python3 -B scripts/verify_controller_contract.py
python3 -B scripts/verify_controller_rbac.py
python3 -B scripts/verify_controller_runtime_contract.py
python3 -B scripts/verify_controller_deployment.py
python3 -B scripts/verify_controller_patch_plan.py
python3 -B scripts/verify_controller_sync.py
python3 -B scripts/verify_controller_status_apply.py
python3 -B scripts/verify_controller_loop.py
python3 -B scripts/verify_controller_resource_budget.py
python3 -B scripts/verify_lightweight_cluster_smoke.py
python3 -B scripts/verify_managed_kubernetes_smoke.py
python3 -B scripts/run_helm_smoke.py
python3 -B scripts/verify_helm_chart.py
python3 -B scripts/verify_kustomize.py
python3 -B scripts/verify_release_archives.py
python3 -B scripts/run_krew_smoke.py
python3 -B scripts/verify_krew_manifest.py
python3 -B scripts/verify_supply_chain.py
python3 -B scripts/verify_security_docs.py
python3 -B scripts/verify_api_freeze.py
python3 -B scripts/verify_docs_freeze.py
python3 -B scripts/verify_live_validation_readiness.py
python3 -B scripts/verify_live_validation_queue.py
python3 -B scripts/verify_live_validation_queue_safety.py
python3 -B scripts/verify_live_evidence_directory_scaffold.py
python3 -B scripts/verify_live_evidence_schema.py
python3 -B scripts/verify_live_evidence_manifest.py
python3 -B scripts/verify_live_evidence_coverage.py
python3 -B scripts/verify_project_governance.py
python3 -B scripts/verify_airgap_bundle.py
python3 -B scripts/verify_agent_help_contract.py
python3 -B scripts/verify_agent_examples.py
python3 -B scripts/verify_kyverno_adapter.py
python3 -B scripts/verify_opa_adapter.py
python3 -B scripts/verify_kube_linter_adapter.py
python3 -B scripts/verify_kube_score_adapter.py
python3 -B scripts/verify_pluto_adapter.py
python3 -B scripts/verify_adapter_contract.py
python3 -B scripts/verify_mcp_contract.py
python3 -B scripts/verify_mcp_docs.py
python3 -B scripts/verify_execute_disabled.py
python3 -B scripts/verify_admission_webhook.py
python3 -B scripts/verify_admission_policy.py
python3 -B scripts/verify_admission_digest_gate.py
python3 -B scripts/verify_admission_audit.py
python3 -B scripts/verify_admission_response.py
python3 -B scripts/verify_admission_server.py
python3 -B scripts/run_admission_kind_smoke.py
python3 -B scripts/generate_release_notes.py --version "$(cat VERSION)" --output -
git diff --check
```

Expected:

- release verification passes;
- unit tests pass;
- release notes render without errors;
- CRD upgrade and rollback fixtures verify offline;
- CRD explain descriptions and example commands verify offline;
- conformance suite verifies upstream N/N-1/N-2 local matrix;
- release taskboard audit verifies status rows, remaining evidence notes, and
  release check count;
- release progress report verifies versioned task status, external gates, live
  readiness, complete tool-ready next actions, blocker summaries, and optional
  evidence directory status; blocker summaries include filtered worklist
  commands and evidence next commands are not truncated;
- version worklist verifies schema `kube-actuary.version-worklist.v1`,
  groups open work by release version with capture-ready/tool-blocked status,
  summarizes every repeated missing-tool and environment blocker with filtered
  worklist drilldown commands, including version-scoped blocker commands,
  filters worklists, next-task selection, iteration packs, and history records
  by capture status, missing tool, or environment status,
  carries those blocker filters through live evidence scaffold and advance
  workflows,
  resolves evidence paths and file readiness for the full local worklist,
  writes local iteration packs with schema `kube-actuary.version-iteration.v1`
  while preserving blocker summaries, drilldown commands, and evidence
  readiness when `--evidence-dir` is used,
  compares packs with schema `kube-actuary.version-iteration-diff.v1`,
  records evidence-aware run history with schema `kube-actuary.version-iteration-history.v1`,
  inspects evidence-aware history status with schema `kube-actuary.version-iteration-history-status.v1`
  in text, JSON, and Markdown while preserving latest blocker summaries and
  drilldown commands, latest run artifact paths, latest run diff summaries,
  next local loop commands, latest environment probe failures, and records
  `status.json` plus `status.md` on request,
  selects the next task with schema `kube-actuary.next-version-task.v1`,
  resolves next-task evidence paths under a requested evidence directory,
  skips completed local evidence file sets when requested,
  and exercises version/open-only filters plus optional environment blockers;
- external gate plan verifies remaining `VERIFY` rows are structured and
  mapped to concrete evidence commands;
- external gate command safety verifies generated external commands stay
  dry-run, read-only, or local evidence-only;
- external gate evidence evaluation maps captured smoke manifests and
  supplemental external evidence back to taskboard rows;
- external evidence builder creates supplemental evidence records from captured
  raw outputs and fails invalid resource-budget samples;
- external evidence bundle records manifest, supplemental evidence, input
  digests, and closure status in one auditable JSON artifact;
- release evidence directory builder validates captured evidence directories
  and writes manifest and bundle artifacts without contacting clusters;
- release evidence status inspector reports partial directory coverage, next
  commands, persisted next-task output, next-task runner status, environment
  metadata, advance workflow status, and next-task file readiness without
  requiring complete release closure; text/Markdown output does not truncate
  local next commands, selected next-task files, or selected next-task
  commands; next commands exclude missing-tool and environment-blocked capture
  commands, and it can also record
  `.kubeactuary/release-evidence-status.json`;
- next-task evidence builder creates supplemental evidence from prepared raw
  files without cluster, cloud, or workload writes;
- clean-artifact verifier proves no generated Python cache directories or
  bytecode files remain in the workspace;
- controller contract emits status-only patch examples and OperationCapsule-only
  watch commands;
- controller RBAC grants only OperationCapsule read/watch and status patch
  permissions;
- controller runtime contract emits health, readiness, metrics, and Lease
  configuration without contacting the cluster;
- controller deployment seed verifies optional probes, resource limits, and
  hardened runtime defaults;
- controller patch plan verifies status-only patches without executing writes;
- controller sync verifies a read-only OperationCapsule list call and disabled
  write execution;
- controller status apply verifies server-side dry-run by default and
  status-only `--execute` shape;
- controller loop verifies repeated read/status-patch ticks stay server-side
  dry-run by default;
- controller resource budget contract, measurement parser, and read-only capture
  helper verify offline;
- lightweight cluster smoke plan and JSON evidence output verify offline;
- managed Kubernetes smoke plan verifies EKS/GKE/AKS current-context evidence
  output offline;
- Helm chart contract and dry-run smoke evidence format verify offline;
- Kustomize base and overlays render with `kubectl kustomize`;
- release archives verify SHA-256 sidecars and install smoke;
- Krew manifest generation verifies platform entries, archive digests, and
  isolated install smoke evidence format;
- SBOM and provenance generation verify archive digests;
- security docs verify policy, threat model, and disclosure process;
- API freeze gate verifies the additive-only public contract and no breaking
  schema diff;
- documentation freeze verifies public docs and examples;
- live validation readiness inventories external tool availability without
  running cluster or cloud checks by default and can probe current cluster
  availability without writes;
- live validation queue emits schema `kube-actuary.live-validation-queue.v1`
  with ordered tool-ready, missing-tool, and environment-blocked evidence
  commands;
- live validation queue safety verifies placeholder and resolved queue commands
  remain dry-run, read-only, or local evidence-only;
- live evidence directory scaffold verifies the local reports/raw/supplemental
  directory layout, generated queue snapshots, next-task artifacts, and
  `--skip-complete-evidence` artifact advancement, blocker-focused next-task
  filters, optional environment probe status, plus
  `kube-actuary.environment-probe.v1` and
  `kube-actuary.environment-blockers.v1` reports;
- next-version task runner verifies selected evidence commands in plan mode and
  fake-run mode before live use;
- version iteration advance verifies selected-task execution or environment
  blocking with blocker-focused filters, before/after evidence-aware history
  recording, and
  `.kubeactuary/next-version-task-run.json` runner status plus
  `.kubeactuary/version-iteration-advance.json` workflow status output,
  including selected blocker status and next-step metadata;
- live evidence schema validates captured smoke reports before they count as
  release evidence;
- live evidence manifest maps captured reports to release gates and records
  report SHA-256 digests;
- live evidence coverage verifies captured run reports cover lightweight,
  managed, Helm, Krew, and admission smoke gates;
- project governance verifies LICENSE, NOTICE, SECURITY, and CONTRIBUTING;
- air-gapped manifest verifies required release and repository artifacts;
- agent help contract verifies schema version and compatibility fields;
- agent examples verify local CI and Codex runbooks without write commands;
- Kyverno adapter verifies pass and fail fixtures;
- OPA adapter verifies pass and fail fixtures;
- kube-linter adapter verifies pass and fail fixtures;
- kube-score adapter verifies pass and fail fixtures;
- Pluto adapter verifies pass and fail fixtures;
- adapter contract verifies common evidence fields and normalized severity;
- MCP contract verifies five safe tools and disabled execute tool;
- MCP docs verify the client config and safe-tool guide;
- disabled-execute verifier proves CLI and MCP surfaces do not expose execute;
- admission webhook prototype verifies optional defaults and `failurePolicy: Ignore`;
- admission policy verifies AI identity selection and required annotations;
- admission digest/gate verifier rejects digest tampering and closed gates;
- admission audit verifier checks audit annotations and incident runbook;
- admission response verifier checks AdmissionReview responses and
  auditAnnotations;
- admission server verifier checks the local `/validate` endpoint without
  cluster access;
- admission kind smoke plan and evidence-output format verify offline;
- no whitespace errors;
- no `__pycache__` directories or Python bytecode files remain.

## Artifact Checks

- [ ] CLI version prints the intended version.
- [ ] `kube-actuary help agents --format json` parses.
- [ ] Agent help JSON includes the expected `schemaVersion` and
      `compatibility.requiredCommandFields`.
- [ ] CRD YAML parses.
- [ ] `kubectl explain` runbook is reviewed for the current CRD.
- [ ] CRD rollback fixture YAML parses.
- [ ] controller dry-run contract check passes.
- [ ] release taskboard audit check passes.
- [ ] release progress check passes.
- [ ] version worklist check passes.
- [ ] external gate plan check passes.
- [ ] external gate command safety check passes.
- [ ] external gate evidence evaluation check passes.
- [ ] external evidence builder check passes.
- [ ] external evidence bundle check passes.
- [ ] release evidence directory check passes.
- [ ] release evidence status check passes.
- [ ] next-task evidence builder check passes through release evidence status.
- [ ] next-version task runner check passes.
- [ ] version iteration advance check passes.
- [ ] clean artifact check passes.
- [ ] controller RBAC check passes.
- [ ] controller runtime contract check passes.
- [ ] controller deployment seed check passes.
- [ ] controller status patch plan check passes.
- [ ] controller read-only sync check passes.
- [ ] controller status apply dry-run check passes.
- [ ] controller loop dry-run check passes.
- [ ] controller resource budget check passes.
- [ ] controller resource capture check passes.
- [ ] lightweight cluster smoke plan and evidence-output check passes.
- [ ] managed Kubernetes smoke plan check passes; run per provider with
      `--run --output <path>` on approved contexts.
- [ ] upstream N/N-1/N-2 conformance suite passes.
- [ ] live kind/minikube/MicroK8s/k3s evidence is attached before claiming
      matrix support.
- [ ] Helm chart check passes; run `scripts/run_helm_smoke.py --run --output <path>` when Helm is available.
- [ ] Kustomize base and overlays render.
- [ ] release archive checksum and install smoke pass.
- [ ] Krew manifest check passes; run Krew smoke with `--run --output <path>`
      when Krew is available.
- [ ] SBOM and provenance checks pass.
- [ ] security policy and threat model check passes.
- [ ] API freeze gate check passes.
- [ ] documentation freeze check passes.
- [ ] live validation readiness check passes.
- [ ] live validation queue check passes.
- [ ] live validation queue safety check passes.
- [ ] live evidence directory scaffold check passes.
- [ ] captured live evidence schema check passes.
- [ ] captured live evidence manifest check passes.
- [ ] captured live evidence coverage check passes.
- [ ] project governance check passes.
- [ ] air-gapped bundle manifest check passes.
- [ ] agent help contract check passes.
- [ ] agent example runbook check passes.
- [ ] Kyverno adapter fixture check passes.
- [ ] OPA adapter fixture check passes.
- [ ] kube-linter adapter fixture check passes.
- [ ] kube-score adapter fixture check passes.
- [ ] Pluto adapter fixture check passes.
- [ ] adapter contract check passes.
- [ ] MCP safe-tool contract check passes.
- [ ] MCP docs and client config check passes.
- [ ] disabled-execute surface check passes.
- [ ] admission webhook prototype check passes; run live kind smoke when kind is available.
- [ ] admission policy allow/deny fixture check passes.
- [ ] admission digest/gate tamper fixture check passes.
- [ ] admission audit fixture and incident runbook check passes.
- [ ] admission response fixture check passes.
- [ ] admission local server check passes.
- [ ] admission kind smoke plan check passes; run with `--run --output <path>`
      when kind is available.
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
