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
  validate, doctor, normalized collector failures, release taskboard audit,
  release progress reporting, version worklist generation, evidence-aware worklist readiness, evidence-aware iteration packs, evidence-aware iteration history, next version task selection, evidence-aware next-task skipping, external gate plan generation, external gate evidence evaluation,
  supplemental external evidence builder, external evidence bundle generation,
  release evidence directory artifact generation, release evidence status inspection,
  clean generated-artifact verification,
  human help, agent JSON help, structured help compatibility, controller dry-run contract, controller RBAC,
  controller runtime contract, controller deployment seed, controller status
  patch plan, controller read-only sync, controller status apply dry-run,
  controller loop dry-run, controller resource budget,
  lightweight cluster smoke harness, upstream conformance suite, Helm chart
  contract, managed Kubernetes smoke harness, Kustomize rendering,
  release archives, Krew manifest generation, SBOM/provenance
  generation, security docs, API freeze compatibility gate, documentation
  freeze and public examples audit, live validation readiness inventory with
  gate-level tool readiness and optional environment probing, live validation
  queue generation, queue command safety,
  and live evidence directory scaffold generation with next-task advancement,
  live evidence schema validation, live evidence manifest generation, live
  evidence coverage validation, next-task evidence build from prepared raw
  files, project governance, air-gapped manifest generation, agent help schema
  compatibility, local CI and Codex agent runbooks, Kyverno adapter fixtures,
  OPA adapter fixtures, kube-linter adapter fixtures, kube-score adapter
  fixtures, Pluto adapter fixtures, adapter
  contract severity normalization, MCP safe-tool contract verification, and
  MCP docs/client config verification, disabled-execute surface verification,
  optional admission webhook prototype, admission identity/annotation policy
  fixtures, admission digest/gate tamper fixtures, admission audit fixtures,
  admission response fixtures, local admission server smoke, and full manifest gate behavior;
- no `__pycache__` directories or Python bytecode files are left behind, and
  local live evidence state remains git-ignored.

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
- conformance suite check prints `conformance-suite: passed`;
- release taskboard check prints `release-taskboard: passed`;
- release progress check prints `release-progress: passed` and confirms
  prepared evidence directories use the persisted live validation queue as the
  next-action source, show every open item in version Markdown/text, and show
  every action blocker plus filtered worklist commands, selected next-task
  file/command details, every runnable tool-ready action and evidence next
  command, persisted queue-source status, and version-iteration advance
  run/history metadata, without recommending environment-blocked capture
  commands or runnable JSON first commands for blocked actions;
- version worklist check prints `version-worklist: passed` and covers complete
  text output, blocker summaries, blocker drilldown commands with evidence-dir
  and version context, blocker-focused filters, and next-task selection;
- evidence-aware worklist output resolves commands and summarizes file
  readiness for every open external task when `--evidence-dir` is used;
- evidence-aware worklist and next-task selection use a prepared live
  validation queue when the evidence directory already contains one;
- prepared-queue worklist and next-task Markdown output show the queue source;
- prepared-queue worklist Markdown shows blocker summaries, missing tools, and
  next steps;
- worklist, next-task, iteration-pack, iteration-history, live scaffold, and
  advance commands preserve version, capture-status, missing-tool,
  environment-status, and environment-reason filters;
- prepared-queue version iteration packs preserve the queue source, blocker
  summaries, and blocker drilldown commands;
- prepared-queue version iteration history records and status preserve the queue source;
- version iteration history status preserves latest blocker summaries and
  drilldown commands in text, JSON, and Markdown output;
- version iteration history status preserves latest run filters in text, JSON,
  Markdown, and recorded status reports;
- version iteration history status preserves selected latest next-task details
  in text, JSON, Markdown, and recorded status reports;
- version iteration history status preserves selected latest next-task evidence
  file details in text, JSON, and Markdown;
- version iteration history status preserves selected latest next-task worklist
  drilldowns in text, JSON, and Markdown;
- version iteration history status preserves latest advance and runner status
  from the evidence directory in text, JSON, and Markdown;
- version iteration history status compares latest advance records against the
  latest next-task selection and reports stale mismatches;
- version iteration history status preserves latest run, worklist, and diff
  artifact paths in text, JSON, Markdown, and recorded status reports;
- version iteration history status preserves latest run diff summaries in text,
  JSON, Markdown, and recorded status reports;
- version iteration history status preserves latest per-version diff summaries
  in text, JSON, Markdown, and recorded status reports;
- version iteration history status preserves latest environment probe failures;
- version iteration history status records `status.json` and `status.md` on request;
- version iteration history status surfaces next local loop commands for
  status refresh and latest-filter reruns;
- prepared-queue scaffold, next-task runner, and advance reports preserve the queue source;
- version iteration packs preserve resolved closure commands, blocker
  summaries, blocker drilldown commands, and evidence readiness when
  `--evidence-dir` is used;
- version iteration history records and inspects evidence readiness deltas
  between runs;
- evidence-aware next-task selection skips completed local evidence file sets
  when `--skip-complete-evidence` is used;
- external gate plan check prints `external-gate-plan: passed`;
- external gate command safety check prints `external-gate-command-safety:
  passed`;
- external gate evidence check prints `external-gate-evidence: passed`;
- external evidence builder check prints `external-evidence-builder: passed`;
- external evidence bundle check prints `external-evidence-bundle: passed`;
- release evidence directory check prints `release-evidence-directory: passed`
  and verifies generated `.kubeactuary` metadata is ignored with custom output
  directories;
- release evidence status check prints `release-evidence-status: passed` and
  verifies persisted next-task output, file readiness, next-task evidence build,
  next-task-run status, environment metadata, advance status, queue-source
  visibility/origin, next-task queue consistency, selected next-task worklist
  drilldowns, version-scoped coverage totals, missing gates, and blocker drilldown commands, runner/evidence-build/advance record
  consistency, legacy
  prepared-record queue-source inference, complete
  text/Markdown next-command and next-task detail output, CLI Markdown status
  output, next-task evidence build Markdown output, and idempotent
  output-exists handling plus
  `.kubeactuary/release-evidence-status.{json,md}` and
  `.kubeactuary/next-task-evidence-build.{json,md}` recording;
- next version task runner check prints `next-version-task-runner: passed`
  and verifies `.kubeactuary/next-version-task-run.{json,md}` recording plus
  queue-source preservation and zero-run reporting for non-`tool-ready`
  selected tasks plus CLI Markdown output;
- version iteration advance check prints `version-iteration-advance: passed`
  and verifies version-scoped selection plus selected blocker status/next-step preservation
  and verifies queue-source-preserving persisted runner and advance status
  reports plus selected worklist drilldowns and CLI Markdown output;
- CRD upgrade fixture check prints `crd-upgrade-fixtures: passed`;
- controller contract check prints `controller-contract: passed`;
- controller RBAC check prints `controller-rbac: passed`;
- controller runtime check prints `controller-runtime: passed`;
- controller deployment check prints `controller-deployment: passed`;
- controller patch plan check prints `controller-patch-plan: passed`;
- controller sync check prints `controller-sync: passed`;
- controller status apply check prints `controller-status-apply: passed`;
- controller loop check prints `controller-loop: passed`;
- controller resource budget check prints `controller-resource-budget: passed`;
- controller resource capture check prints `controller-resource-capture: passed`;
- lightweight cluster smoke check prints `lightweight-cluster-smoke: passed`;
- managed Kubernetes smoke check prints `managed-kubernetes-smoke: passed`;
- Helm chart check prints `helm-chart: passed`;
- Kustomize check prints `kustomize: passed`;
- release archive check prints `release-archives: passed`;
- Krew manifest check prints `krew-manifest: passed`;
- supply-chain check prints `supply-chain: passed`;
- security docs check prints `security-docs: passed`;
- API freeze check prints `api-freeze: passed`;
- docs freeze check prints `docs-freeze: passed`;
- live validation readiness check prints `live-validation-readiness: passed`;
- live validation queue check prints `live-validation-queue: passed`;
- live validation queue safety check prints `live-validation-queue-safety: passed`;
- live evidence directory scaffold check prints
  `live-evidence-directory-scaffold: passed` and verifies
  `--skip-complete-evidence` next-task advancement, blocker-focused next-task
  filters, optional environment probe persistence, plus
  `kube-actuary.environment-probe.v1` and
  `kube-actuary.environment-blockers.v1` output;
- live evidence schema check prints `live-evidence-schema: passed`;
- live evidence manifest check prints `live-evidence-manifest: passed`;
- live evidence coverage check prints `live-evidence-coverage: passed`;
- project governance check prints `project-governance: passed`;
- airgap bundle check prints `airgap-bundle: passed`;
- agent help contract check prints `agent-help-contract: passed`;
- agent examples check prints `agent-examples: passed`;
- Kyverno adapter check prints `kyverno-adapter: passed`;
- OPA adapter check prints `opa-adapter: passed`;
- kube-linter adapter check prints `kube-linter-adapter: passed`;
- kube-score adapter check prints `kube-score-adapter: passed`;
- Pluto adapter check prints `pluto-adapter: passed`;
- adapter contract check prints `adapter-contract: passed`;
- MCP contract check prints `mcp-contract: passed`;
- MCP docs check prints `mcp-docs: passed`;
- disabled-execute check prints `execute-disabled: passed`;
- admission webhook check prints `admission-webhook: passed`;
- admission policy check prints `admission-policy: passed`;
- admission digest/gate check prints `admission-digest-gate: passed`;
- admission audit check prints `admission-audit: passed`;
- admission response check prints `admission-response: passed`;
- admission server check prints `admission-server: passed`;
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
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml charts/kubeactuary/Chart.yaml charts/kubeactuary/values.yaml deploy/kustomize/base/kustomization.yaml deploy/kustomize/overlays/controller-namespace/kustomization.yaml deploy/kustomize/overlays/controller-cluster/kustomization.yaml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml deploy/admission/validatingwebhookconfiguration.yaml examples/operationcapsule-scale.yaml examples/configmap-demo.yaml examples/configmap-demo.rollback.yaml
```

Expected:

- JSON examples parse;
- schema JSON parses;
- GitHub Actions workflow, Helm chart metadata, Kustomize manifests, CRD YAML,
  CRD rollback fixture YAML, controller RBAC YAML, admission webhook YAML, and
  example YAML files parse.

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
- conformance suite verifies the upstream `1.36`, `1.35`, and `1.34` local
  matrix against CRD compatibility, upgrade fixtures, and explain quality;
- release taskboard audit verifies status rows, remaining evidence notes, and
  the release suite check count;
- release progress verifier checks versioned task status, external gates, live
  readiness, tool-ready next actions, optional evidence directory status, and
  `not-prepared` guidance for missing evidence directories, plus selected
  next-task, runner failure, environment, advance status, and repeated blocker
  summaries with filtered worklist commands in Markdown and text output; it
  also checks tool-ready action and evidence next-command output is not truncated;
- version worklist verifier checks version-grouped open work, local iteration
  pack generation, iteration pack diffs, iteration history recording,
  history status inspection, evidence-aware worklist readiness,
  evidence-aware iteration packs, evidence-aware iteration history,
  next-task selection, evidence-directory command
  resolution, completed-evidence skipping, capture-ready items, tool-blocked
  items, version/open-only filters, blocker summaries, evidence-aware and
  version-scoped blocker drilldown commands, environment-reason drilldowns,
  blocker-focused filters, and
  optional environment blockers;
- external gate plan verifier maps remaining VERIFY rows to local evidence
  commands and requires zero DOING/TODO rows;
- external gate evidence verifier maps captured smoke manifests and
  supplemental external evidence back to taskboard rows;
- external evidence builder verifier validates supplemental evidence records
  for kubectl explain, controller resource budget, and controller loop output;
- external evidence bundle verifier records live manifest, supplemental
  evidence, input SHA-256 digests, and closure status in one JSON artifact;
- release evidence directory verifier builds manifest and bundle artifacts from
  one local evidence directory and ignores generated artifacts on rerun;
- release evidence status verifier reports partial and complete evidence
  directory coverage plus persisted next-task output and file readiness without
  requiring cluster or cloud access, and checks unprepared evidence directory
  guidance for local next-task evidence builds, runner failure summaries,
  resolved prepared-queue command priority, selected next-task worklist
  drilldowns, version-scoped coverage totals, missing gates, and blocker drilldown commands, runner/advance record consistency,
  and probe-first guidance after failed runner attempts or environment blockers;
- next-task evidence builder verifier coverage creates supplemental evidence
  from prepared raw files, records passed and missing-source status reports, and
  skips existing outputs without cluster, cloud, or workload writes;
- next version task runner verifier validates selected commands, stays
  plan-by-default, and with fake kubectl produces raw and supplemental evidence
  for the selected task, while reporting a prepare command for unprepared
  evidence directories and preserving failed-run summaries;
- version iteration advance verifier wraps the selected-task runner with
  version-scoped, probe-aware before/after evidence-aware history recording and
  validates the resulting diff or zero-run environment-blocked runner record
  plus blocked history snapshot and selected worklist drilldowns;
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
- controller Deployment seed runs only the local `serve` runtime and includes
  probes, resource limits, and hardened security defaults;
- controller patch planner emits status-only patch plans and keeps
  `writeExecution` disabled;
- controller sync executes only `kubectl get` for OperationCapsules and emits
  status-only patch plans with `writeExecution` disabled;
- controller status apply defaults to `--dry-run=server` and keeps live status
  writes behind explicit `--execute`;
- controller loop repeats `kubectl get` and status-only patch ticks while
  keeping default patches server-side dry-run;
- controller resource budget helper sets idle <50m CPU and <64Mi memory targets,
  parses `kubectl top` samples, and emits structured JSON measurement evidence;
- controller resource capture helper stays plan-by-default, runs only read-only
  `kubectl top` with `--run`, preserves raw output, and leaves supplemental
  evidence buildable;
- lightweight cluster smoke helper uses server-side dry-run plans, verifies JSON
  evidence output, and covers kind, minikube, MicroK8s, and k3s without default
  writes;
- managed Kubernetes smoke helper verifies EKS, GKE, and AKS current-context
  plans and JSON evidence without default writes or cloud credential mutation;
- Helm chart packages the CRD under `crds/`, keeps optional controller RBAC
  disabled by default, and verifies dry-run smoke evidence output;
- Kustomize base renders only the CRD, while controller overlays add only
  optional RBAC;
- release archive generator emits multi-target archives, SHA-256 sidecars, and
  install smoke for CLI/plugin/controller;
- Krew manifest generator maps `kubectl-actuary` and adjacent `kube-actuary`
  helper for each archive target and verifies isolated install smoke evidence;
- SBOM/provenance generator records file hashes and release archive subjects;
- security docs verifier requires supported versions, disclosure process,
  threat model, mitigations, and residual risk sections;
- API freeze verifier guards the additive-only public JSON Schema and CRD
  contract against breaking schema diff;
- docs freeze verifier checks public docs, capsule examples, YAML examples, and
  agent runbooks;
- live validation readiness verifier inventories remaining external validation
  gates and missing local tools without contacting clusters or cloud APIs by
  default, and verifies optional read-only environment probing with fake
  kubectl plus stable probe reason classification;
- live validation queue verifier checks schema
  `kube-actuary.live-validation-queue.v1`, ordered evidence commands, and
  tool-ready, missing-tool, or environment-blocked status plus environment
  probe reasons for each external gate;
- live validation queue safety verifier checks placeholder and resolved queue
  commands stay dry-run, read-only, or local evidence-only;
- live evidence directory scaffold verifier checks prepared `reports/`, `raw/`,
  `supplemental/`, and `.kubeactuary/` directories plus queue snapshots and
  next-task artifacts, preserves blocker-focused filters, then advances past
  completed evidence file sets when `--skip-complete-evidence` is used;
- live evidence schema verifier validates all supported smoke report schemas;
- live evidence manifest verifier maps captured reports to release gates and
  records report SHA-256 digests without contacting clusters;
- live evidence coverage verifier requires passing run evidence for all
  lightweight providers, managed providers, Helm, Krew, and admission gates;
- project governance verifier requires LICENSE, NOTICE, SECURITY, and
  CONTRIBUTING;
- air-gapped manifest generator lists required release and repository artifacts
  with SHA-256 digests;
- agent help contract verifier requires schema version, compatibility metadata,
  top-level fields, and per-command required fields;
- agent example verifier requires local CI and Codex runbooks and rejects direct
  Kubernetes write instructions;
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
- MCP contract verification exposes only the five safe tools and keeps
  `execute_approved_capsule` disabled;
- MCP docs verifier checks `examples/mcp-client-config.json` and the safe-tool
  guide;
- disabled-execute verifier requires CLI command help and agent JSON to omit
  execute tools and MCP calls to reject `execute_approved_capsule`;
- admission webhook prototype verifier requires `failurePolicy: Ignore`,
  opt-in namespace selection, and bounded timeout;
- admission policy verifier allows non-AI identities, requires capsule and
  digest annotations for selected AI writers, and denies missing annotations;
- admission digest/gate verifier rejects tampered digests and referenced
  capsules with closed gates;
- admission audit verifier requires audit annotations for capsule, digest,
  gate, decision, and reason plus an incident runbook;
- admission response verifier requires AdmissionReview responses and
  auditAnnotations;
- admission server verifier exercises the local `/validate` endpoint without
  Kubernetes API access;
- admission kind smoke helper verifies server-side dry-run webhook checks and
  loopback-only local admission server evidence output;
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
  release notes dry-run, release taskboard audit, release progress, version worklist, external gate plan, external gate command safety, external gate evidence,
  evidence-aware worklist readiness, evidence-aware iteration packs, evidence-aware iteration history, evidence-aware next-task skipping, external evidence builder, external evidence bundle, release evidence directory, release evidence status, next-task evidence build, next-version task run, version iteration advance,
  CRD compatibility smoke, CRD explain quality, CRD
  upgrade fixtures, conformance suite, controller contract, controller RBAC,
  controller runtime, controller deployment, controller patch plan, controller
  sync, controller status apply, controller loop, controller resource budget, controller resource capture, lightweight cluster smoke, digest, CRD render,
  managed Kubernetes smoke, Helm chart, Kustomize, release archives, Krew manifest, supply chain,
  security docs, API freeze, docs freeze, live validation readiness, live validation queue, live validation queue safety, live evidence directory scaffold, live
  evidence schema, live evidence manifest, live evidence coverage, project governance, air-gapped bundle, agent help contract, agent examples, Kyverno
  adapter, OPA adapter, kube-linter adapter, kube-score adapter, Pluto adapter, adapter
  contract, MCP contract, MCP docs, disabled-execute check, admission webhook,
  admission policy, admission digest/gate, admission audit, admission response,
  admission server, admission kind smoke, gate behavior, JSON/YAML parsing, and
  `git diff --check`.
