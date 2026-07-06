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
verification: passed (66 checks)
Ran 100 tests
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
- upstream N/N-1/N-2 conformance suite verification;
- pure controller reconcile model computes status-only patches;
- controller watch contract stays scoped to OperationCapsule resources;
- controller RBAC grants OperationCapsule read/watch and status-only write
  permissions;
- controller runtime contract emits health, readiness, Prometheus metrics, and
  leader-election Lease configuration;
- controller Deployment seed with local `serve` runtime, probes, resource
  limits, and hardened security defaults;
- controller status patch planner with status-only patch bodies and disabled
  write execution;
- controller read-only sync that executes only `kubectl get` for
  OperationCapsules and emits disabled-write status patch plans;
- controller status apply dry-run with explicit status-only execute mode;
- controller status loop dry-run with repeated read/status-patch ticks;
- controller resource budget contract and `kubectl top` measurement parser;
- lightweight cluster smoke plan and JSON evidence output for kind, minikube,
  MicroK8s, and k3s;
- managed Kubernetes smoke plan and JSON evidence output for EKS, GKE, and AKS;
- Helm chart seed for CRD packaging, optional controller RBAC, and dry-run
  smoke evidence output;
- Kustomize base and controller RBAC overlays;
- multi-target release archives with SHA-256 sidecars and install smoke;
- Krew manifest generator with archive digest validation and isolated install
  smoke evidence output;
- SBOM and provenance generation with archive digest verification;
- security policy, threat model, and disclosure process verification;
- API freeze and additive compatibility gate verification;
- documentation freeze and public examples audit verification;
- live validation readiness inventory verification;
- live evidence schema validation for captured smoke reports;
- live evidence manifest generation for captured smoke reports;
- live evidence coverage validation for captured smoke report manifests;
- project governance, contribution, notice, and license verification;
- air-gapped artifact manifest and offline checklist verification;
- agent help schema compatibility verification;
- local CI and Codex agent runbook verification;
- disabled execute surface verification;
- optional admission webhook prototype verification;
- AI identity selector and admission annotation allow/deny verification;
- admission digest and gate tamper fixture verification;
- admission audit annotation fixture and incident runbook verification;
- AdmissionReview response and audit annotation generation verification;
- local admission HTTP server verification;
- optional admission kind smoke evidence output verification;
- Kyverno policy adapter pass/fail fixture verification;
- OPA/Rego policy adapter pass/fail fixture verification;
- kube-linter policy adapter pass/fail fixture verification;
- kube-score policy adapter pass/fail fixture verification;
- Pluto deprecated API adapter pass/fail fixture verification;
- common adapter evidence contract and normalized severity verification;
- MCP safe-tool JSON-RPC contract verification;
- MCP docs and client config verification;
- GitHub Actions workflow YAML parsing;
- release notes dry-run generation;
- release taskboard status and check-count audit;
- external gate plan generation for remaining VERIFY rows;
- external gate evidence evaluation for captured smoke manifests plus
  supplemental external evidence;
- supplemental external evidence builder for raw live outputs;
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
python3 -B scripts/verify_conformance_suite.py
python3 -B scripts/verify_release_taskboard.py
python3 -B scripts/verify_external_gate_plan.py
python3 -B scripts/verify_external_gate_evidence.py
python3 -B scripts/verify_external_evidence_builder.py
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
- conformance suite prints `conformance-suite: passed`;
- release taskboard check prints `release-taskboard: passed`;
- external gate plan check prints `external-gate-plan: passed`;
- external gate evidence check prints `external-gate-evidence: passed`;
- external evidence builder check prints `external-evidence-builder: passed`;
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
- admission kind smoke plan prints `admission-kind-smoke: plan`;
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
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml charts/kubeactuary/Chart.yaml charts/kubeactuary/values.yaml deploy/kustomize/base/kustomization.yaml deploy/kustomize/overlays/controller-namespace/kustomization.yaml deploy/kustomize/overlays/controller-cluster/kustomization.yaml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml deploy/admission/validatingwebhookconfiguration.yaml examples/operationcapsule-scale.yaml examples/configmap-demo.yaml examples/configmap-demo.rollback.yaml /private/tmp/kubeactuary-render-v020.yaml
```

Result:

- example capsule JSON files parse;
- schema JSON parses;
- GitHub Actions workflow, Helm chart metadata, Kustomize manifests, CRD YAML,
  rollback fixture YAML, controller RBAC YAML, admission webhook YAML, CR
  example YAML, manifest examples, and generated CRD object YAML parse.

### Cache Check

```sh
find . -name __pycache__ -type d -print
```

Result:

- no `__pycache__` directories found.

## Release Judgment

v0.2.0 is suitable as a local-first evidence collector alpha release.

It is not production-ready as a live controller or admission system. The current
controller work is an offline status reconcile contract plus a read-only sync
planner, not a status-writing controller.
