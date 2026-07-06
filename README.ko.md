# KubeActuary

<p align="center">
  <img src="assets/brand/kubeactuary-symbol.png" alt="KubeActuary symbol" width="180">
</p>

> AI가 Kubernetes를 조작하기 전에 증거를 들고 오게 만드는 실행 계약 CLI.

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.x-3776AB)](bin/kube-actuary)
[![Kubernetes](https://img.shields.io/badge/kubernetes-CRD%20seed-326CE5)](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)

[English](README.md) | 한국어

KubeActuary는 AI 에이전트에게 무제한 `kubectl` write 권한을 바로 주지 않기
위한 model-free CLI이자 Kubernetes-native 실행 계약입니다. AI는 작업을 제안할
수 있지만, 실행 후보가 되려면 먼저 증거를 가진 `OperationCapsule`을 만들어야
합니다.

```text
AI / 사람의 의도
  -> OperationCapsule
  -> 증거 수집
  -> 게이트 판정
  -> 사람, CI, GitOps 또는 향후 제한된 executor 실행
```

KubeActuary는 또 다른 Kubernetes 챗봇이 아닙니다. 챗봇 아래에 있어야 하는
실행 경계입니다.

## 문제

AI와 Kubernetes를 연결하는 도구는 이미 많습니다.

- `kubectl-ai`는 자연어를 Kubernetes 작업으로 바꿀 수 있습니다.
- `k8sgpt`는 클러스터 문제를 분석하고 설명할 수 있습니다.
- MCP 서버는 클러스터 도구를 에이전트에게 노출할 수 있습니다.
- Kyverno, OPA, kube-linter, kube-score, Polaris, Trivy는 정책, 보안,
  readiness를 검사할 수 있습니다.
- GitOps는 원하는 상태를 reconcile할 수 있습니다.

하지만 아직 작은 공통 계약이 부족합니다.

> AI가 만든 Kubernetes 작업이 실제로 무언가를 바꾸기 전에 어떤 증거를 가져야
> 하는가?

KubeActuary는 이 질문에 `OperationCapsule`로 답합니다.

## 핵심 개념: OperationCapsule

`OperationCapsule`은 이식 가능한 작업 기록입니다.

| 필드 | 목적 |
| --- | --- |
| Intent | 이 작업이 필요한 이유 |
| Proposed action | 명령 또는 manifest 경로 |
| Target | 리소스, 네임스페이스, 범위, verb |
| Risk | 기본 blast radius 추정 |
| Required evidence | auth, dry-run, diff, rollback, approval, post-check |
| Status evidence | 첨부된 증거 기록 |
| Gate | 필수 증거가 성공해야 열림 |

캡슐은 AI가 만들고, 사람이 검토하고, Git에 저장하고, CI에서 검증하고,
Kubernetes CRD 객체로 렌더링하고, 향후 controller가 소비할 수 있습니다.

## v0.2.0에서 되는 것

- `kubectl` 명령 또는 manifest 경로에서 로컬 operation capsule 생성
- 대상, 위험도, 상태, 증거 확인
- 클러스터에 접근하지 않는 capsule JSON 구조 검증
- 로컬 runtime과 `kubectl` client 진단
- 수동 증거 첨부
- `kubectl auth can-i` 증거 수집
- manifest 기반 작업의 server-side dry-run 증거 수집
- manifest 기반 작업의 `kubectl diff` 증거 수집
- 명시적인 rollback 명령 또는 manifest 증거 첨부
- post-change health-plan 증거 첨부
- 감사용 deterministic spec digest 출력
- 누락/실패 증거 검증
- 실행 게이트 open/closed 판정
- 로컬 캡슐을 Kubernetes `OperationCapsule` CRD 객체로 렌더링
- 로컬 캡슐 상태를 CRD status field와 condition mapping으로 렌더링
- `kubectl` 플러그인 진입점 제공
- JSON Schema와 CRD seed 제공

v0.2.0에서 하지 않는 것:

- 실제 클러스터 write 실행 없음
- 클러스터 안에서 LLM 실행 없음
- controller 필수 아님
- admission webhook 없음
- 외부 Python 패키지 의존성 없음

## 빠른 시작

고위험 draft 생성:

```sh
python3 bin/kube-actuary draft \
  --intent "increase checkout API capacity for expected traffic" \
  --command "kubectl scale deployment checkout-api --replicas=6 -n prod" \
  --actor "ai-agent" \
  --out /tmp/scale.capsule.json
```

확인:

```sh
python3 bin/kube-actuary inspect /tmp/scale.capsule.json
```

캡슐 구조 검증:

```sh
python3 bin/kube-actuary validate /tmp/scale.capsule.json
```

`validate`는 로컬 capsule 계약을 확인합니다. 증거 완결성은 `verify`와
`gate`가 판단합니다.

로컬 전제조건 확인:

```sh
python3 bin/kube-actuary doctor
```

이 캡슐은 아직 제안일 뿐이므로 게이트가 닫힙니다.

```sh
python3 bin/kube-actuary gate /tmp/scale.capsule.json
```

승인 증거 첨부:

```sh
python3 bin/kube-actuary attach-evidence /tmp/scale.capsule.json \
  --id owner-approval \
  --summary "checkout service owner approved the scale-up window" \
  --actor "platform-reviewer" \
  --out /tmp/scale.with-approval.json
```

제안된 write 명령을 실행하지 않고 권한 증거만 수집:

```sh
python3 bin/kube-actuary collect auth /tmp/scale.with-approval.json \
  --out /tmp/scale.with-auth.json
```

manifest 기반 변경은 클러스터 write를 저장하지 않고 preflight 증거를 수집할 수
있습니다.

```sh
python3 bin/kube-actuary collect dry-run /tmp/apply.capsule.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-dry-run.json

python3 bin/kube-actuary collect diff /tmp/apply.with-dry-run.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-diff.json
```

rollback과 post-change health-plan 증거 첨부:

```sh
python3 bin/kube-actuary collect rollback /tmp/apply.with-diff.json \
  --manifest examples/configmap-demo.rollback.yaml \
  --out /tmp/apply.with-rollback.json

python3 bin/kube-actuary collect health-plan /tmp/apply.with-rollback.json \
  --out /tmp/apply.with-health.json
```

로컬 캡슐을 Kubernetes 리소스로 렌더링:

```sh
python3 bin/kube-actuary render-crd examples/read-pods.verified.capsule.json \
  --name read-pods \
  --namespace default
```

포함된 read-only 예제 검증:

```sh
python3 bin/kube-actuary verify examples/read-pods.verified.capsule.json
python3 bin/kube-actuary gate examples/read-pods.verified.capsule.json
```

예상 결과:

```text
gate: open
id: opcap-example-read-pods
risk: low
command: kubectl get pods -n default
```

## CLI

```text
draft              OperationCapsule draft 생성
inspect            대상, 위험도, 상태, 증거 요약
validate           capsule JSON 구조 검증
doctor             로컬 runtime과 kubectl 진단
attach-evidence    수동 증거 첨부
collect auth       kubectl auth can-i 증거 수집
collect dry-run    server-side dry-run 증거 수집
collect diff       kubectl diff 증거 수집
collect rollback   rollback 명령 또는 manifest 증거 첨부
collect health-plan post-change check 증거 첨부
digest             deterministic capsule spec digest 출력
help               workflow, safety, evidence, agent 안내 출력
verify             필수 증거 확인
gate               실행 게이트 open/closed 출력
render-crd         캡슐을 Kubernetes CRD 객체로 렌더링
demo               고위험 샘플 캡슐 출력
```

버전 확인:

```sh
python3 bin/kube-actuary --version
```

사람이 읽는 help:

```sh
python3 bin/kube-actuary help
python3 bin/kube-actuary help workflow
python3 bin/kube-actuary help safety
```

에이전트가 읽는 help:

```sh
python3 bin/kube-actuary help agents --format json
```

JSON help에는 command safety, cluster access, evidence id, 안정적인 exit code
의미, CLI가 절대 실행하지 않는 작업, agent integration용 versioned
`schemaVersion`/`compatibility` 계약이 들어갑니다.

## kubectl 플러그인

Kubernetes는 `PATH`에 있는 `kubectl-*` 실행 파일을 플러그인으로 인식합니다.
이 저장소에는 `bin/kubectl-actuary`가 포함되어 있습니다.

```sh
export PATH="$PWD/bin:$PATH"
kubectl actuary draft \
  --intent "inspect pods" \
  --command "kubectl get pods -n default"
```

## Kubernetes-native 방향

CRD seed가 포함되어 있습니다.

- [deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)
- [examples/operationcapsule-scale.yaml](examples/operationcapsule-scale.yaml)

설계 제약:

- namespaced `OperationCapsule` 리소스 하나부터 시작
- 증거는 우선 embedded 방식, 별도 `Evidence` CRD는 나중에 판단
- controller는 KubeActuary 리소스만 watch
- cluster-wide scan 금지
- in-cluster LLM 없음
- 첫 controller 버전에서 write 실행 없음

## Safety Model

KubeActuary는 제안, 증거, 승인, 실행을 분리합니다.

| 책임 | 대표 actor |
| --- | --- |
| 제안 | AI agent, human, CI |
| 증거 수집 | CLI, CI, policy tools |
| 승인 | human/platform owner |
| 실행 | human, GitOps, future bounded executor |

고위험 AI 제안은 존재할 수 있지만, 클러스터를 변경할 권한은 별도 증거와 게이트
통과 전까지 주어지지 않습니다. 이 분리가 핵심입니다.

## 저장소 구조

```text
bin/
  kube-actuary                 CLI
  kube-actuary-controller      dry-run controller reconcile helper
  kubectl-actuary              kubectl plugin entrypoint
CONTRIBUTING.md                contribution and safety boundary guide
controller/
  reconcile.py                 순수 OperationCapsule status reconcile 모델
.github/workflows/
  ci.yml                       GitHub Actions 검증 workflow
SECURITY.md                    security policy와 disclosure process
NOTICE                         project notice and attribution status
charts/
  kubeactuary/                 Helm chart seed
deploy/crds/
  operationcapsules...yaml     CRD seed
  fixtures/                    CRD upgrade와 rollback fixture
deploy/controller/
  *-rbac.yaml                  optional controller RBAC manifest
  deployment.yaml              optional controller runtime Deployment seed
deploy/admission/
  validatingwebhookconfiguration.yaml optional admission webhook prototype
deploy/kustomize/
  base/                        CRD-only Kustomize base
  overlays/                    optional controller RBAC overlays
docs/
  admission.md                optional admission prototype and safety defaults
  admission-kind-smoke.md     optional kind admission smoke runbook
  admission-incident-runbook.md admission audit incident runbook
  api-freeze.md               additive API freeze and compatibility gate
  conformance.md              upstream N/N-1/N-2 conformance suite
  docs-freeze.md              release-candidate public docs checklist
  threat-model.md             project threat model
  collectors.md                evidence collector 계약
  landscape.md                 생태계 조사
  paradigm.md                  운영 모델
  project-assessment.md        현재 성숙도 평가
  release-checklist.md         릴리스 gate 체크리스트
  release-taskboard.md         로컬 v1.0 taskboard
  release-archives.md          release archive build and verification
  supply-chain.md              SBOM and provenance generation
  air-gapped-install.md        offline install artifact checklist
  krew.md                      Krew manifest generation and verification
  helm-smoke.md                Helm template and dry-run install smoke runbook
  live-validation.md           external live validation evidence ledger
  managed-kubernetes-smoke.md  EKS/GKE/AKS smoke runbook
  mcp.md                       MCP client config and safe-tool guide
  policy-adapters.md           policy evidence adapter contracts
  kustomize.md                 Kustomize install and verification runbook
  lightweight-cluster-smoke.md kind/minikube/MicroK8s/k3s smoke runbook
  kubernetes-compatibility.md  Kubernetes와 managed-service 호환성
  crd-upgrade-rollback.md      CRD fixture upgrade/rollback runbook
  controller.md                저부하 controller 설계와 계약
  kubectl-explain.md           kubectl explain quality runbook
  roadmap.md                   개발 계획
  v0.1.0.md                    alpha release 목표
  test-plan-v0.2.0.md          v0.2.0 release test plan
  test-results-v0.2.0.md       최신 검증 결과
  test-plan-v0.1.0.md          release test plan
  test-results-v0.1.0.md       v0.1.0 검증 결과
  crd-design.md                Kubernetes-native 설계
  interoperability.md          CLI, MCP, GitOps, admission 계약
  novelty-check.md             신규성 경계
examples/
  *.capsule.json               로컬 capsule 예제
  operationcapsule-scale.yaml  CRD 예제
  mcp-client-config.json       safe MCP client config example
  agent-local-ci.runbook.md    local CI agent workflow runbook
  agent-codex-workflow.runbook.md Codex agent workflow runbook
schemas/
  operation-capsule...json     JSON Schema
  api-freeze.v0.9.2.json       frozen public API compatibility contract
scripts/
  generate_release_notes.py    release notes dry-run 생성기
  verify_release_taskboard.py  local release taskboard audit
  generate_release_progress.py versioned release progress report generator with blocker summary
  verify_release_progress.py   release progress verifier
  kube-actuary.release-progress.v1 release progress schema
  generate_version_worklist.py version-grouped task worklist generator with filters and evidence readiness
  prepare_version_iteration.py local version iteration pack generator with evidence readiness
  compare_version_iterations.py local version iteration diff generator
  record_version_iteration.py local version iteration history recorder with evidence readiness
  inspect_version_history.py local version iteration history inspector with evidence status
  select_next_version_task.py local next version task selector with evidence skip support
  verify_version_worklist.py version worklist verifier
  kube-actuary.version-worklist.v1 version worklist schema
  kube-actuary.version-iteration.v1 version iteration schema
  kube-actuary.version-iteration-diff.v1 version iteration diff schema
  kube-actuary.version-iteration-history.v1 version iteration history schema
  kube-actuary.version-iteration-history-status.v1 version iteration history status schema
  kube-actuary.next-version-task.v1 next version task schema
  generate_external_gate_plan.py external verification gate plan generator
  verify_external_gate_plan.py external verification gate plan verifier
  verify_external_gate_command_safety.py external gate command safety verifier
  evaluate_external_gate_evidence.py external gate evidence evaluator
  verify_external_gate_evidence.py external gate evidence verifier
  build_external_evidence.py supplemental external evidence builder
  verify_external_evidence_builder.py supplemental evidence builder verifier
  kube-actuary.external-evidence.v1 supplemental evidence schema
  build_external_evidence_bundle.py external evidence bundle builder
  verify_external_evidence_bundle.py external evidence bundle verifier
  kube-actuary.external-evidence-bundle.v1 external evidence bundle schema
  build_release_evidence_directory.py release evidence directory builder
  verify_release_evidence_directory.py release evidence directory verifier
  inspect_release_evidence_directory.py release evidence, next-task, runner, environment, and advance status inspector/recorder
  build_next_task_evidence.py local next-task supplemental evidence builder
  verify_release_evidence_status.py release evidence status verifier
  kube-actuary.release-evidence-status.v1 release evidence status schema
  release-evidence-status.json persisted release evidence status report
  kube-actuary.next-task-evidence-build.v1 next task evidence build schema
  verify_clean_artifacts.py generated Python cache artifact verifier
  verify_crd_compatibility.py  offline CRD compatibility smoke check
  verify_crd_explain_quality.py offline kubectl explain quality check
  verify_crd_upgrade_fixtures.py offline CRD upgrade fixture check
  verify_controller_contract.py offline controller contract check
  verify_controller_rbac.py    offline controller RBAC check
  verify_controller_runtime_contract.py offline controller runtime check
  verify_controller_deployment.py optional controller Deployment seed check
  verify_controller_patch_plan.py status patch plan verifier
  verify_controller_sync.py       read-only controller sync verifier
  verify_controller_status_apply.py status patch dry-run verifier
  verify_controller_loop.py   controller loop dry-run verifier
  verify_controller_resource_budget.py offline controller resource budget check
  measure_controller_resources.py kubectl top budget measurement helper with text/JSON output
  capture_controller_resource_budget.py read-only kubectl top evidence capture helper (`controller-resource-capture`)
  verify_controller_resource_capture.py controller resource evidence capture verifier
  run_lightweight_cluster_smoke.py lightweight cluster smoke harness with JSON evidence output
  verify_lightweight_cluster_smoke.py offline smoke harness check
  verify_conformance_suite.py upstream N/N-1/N-2 conformance verifier
  run_managed_kubernetes_smoke.py EKS/GKE/AKS smoke harness
  verify_managed_kubernetes_smoke.py offline managed smoke verifier
  run_helm_smoke.py           Helm template and dry-run install smoke harness
  verify_helm_chart.py        offline Helm chart contract check
  verify_kustomize.py         Kustomize render check
  package_release_archives.py release archive generator
  verify_release_archives.py  archive checksum and install smoke
  generate_krew_manifest.py   Krew manifest generator
  run_krew_smoke.py           Krew install smoke harness with isolated KREW_ROOT
  verify_krew_manifest.py     offline Krew manifest check
  generate_sbom.py            CycloneDX SBOM generator
  generate_provenance.py      release archive provenance generator
  verify_supply_chain.py      SBOM/provenance verifier
  verify_security_docs.py     security policy and threat model verifier
  verify_api_freeze.py        additive API freeze verifier
  verify_docs_freeze.py       public docs and examples verifier
  verify_live_validation_readiness.py external validation readiness inventory and optional environment probe
  generate_live_validation_queue.py live validation queue generator with optional environment probe
  verify_live_validation_queue.py live validation queue verifier
  verify_live_validation_queue_safety.py live validation queue command safety verifier
  kube-actuary.live-validation-queue.v1 live validation queue schema
  prepare_live_evidence_directory.py live evidence directory scaffold generator with probe-aware next-task advancement
  kube-actuary.environment-probe.v1 environment probe report schema
  kube-actuary.environment-blockers.v1 environment blocker report schema
  run_next_version_task.py selected next-task plan/run/record helper
  verify_next_version_task_runner.py selected next-task runner verifier
  kube-actuary.next-version-task-run.v1 selected next-task runner schema
  next-version-task-run.json persisted selected runner status report
  advance_version_iteration.py selected next-task runner plus before/after history and runner status recorder
  verify_version_iteration_advance.py version iteration advance verifier
  kube-actuary.version-iteration-advance.v1 version iteration advance schema
  version-iteration-advance.json persisted advance workflow status report
  verify_live_evidence_directory_scaffold.py live evidence directory scaffold verifier
  validate_live_evidence.py   captured live evidence JSON validator
  verify_live_evidence_schema.py live evidence schema verifier
  build_live_evidence_manifest.py captured evidence manifest builder
  verify_live_evidence_manifest.py live evidence manifest verifier
  check_live_evidence_coverage.py live evidence release-gate coverage checker
  verify_live_evidence_coverage.py live evidence coverage verifier
  verify_project_governance.py contribution, notice, and license verifier
  generate_airgap_manifest.py air-gapped artifact manifest generator
  verify_airgap_bundle.py     offline bundle verifier
  verify_agent_help_contract.py agent help schema contract verifier
  verify_agent_examples.py    local CI/Codex runbook verifier
  adapt_kyverno_evidence.py   Kyverno output to evidence adapter
  verify_kyverno_adapter.py   Kyverno adapter fixture verifier
  adapt_opa_evidence.py       OPA output to evidence adapter
  verify_opa_adapter.py       OPA adapter fixture verifier
  adapt_kube_linter_evidence.py kube-linter output to evidence adapter
  verify_kube_linter_adapter.py kube-linter adapter fixture verifier
  adapt_kube_score_evidence.py kube-score output to evidence adapter
  verify_kube_score_adapter.py kube-score adapter fixture verifier
  adapt_pluto_evidence.py     Pluto output to evidence adapter
  verify_pluto_adapter.py     Pluto adapter fixture verifier
  verify_adapter_contract.py  common adapter contract verifier
  kube_actuary_mcp_server.py  safe MCP/JSON-RPC stdio wrapper
  verify_mcp_contract.py      MCP safe-tool contract verifier
  verify_mcp_docs.py          MCP docs and client config verifier
  verify_execute_disabled.py  disabled execute surface verifier
  verify_admission_webhook.py optional admission prototype verifier
  evaluate_admission_review.py offline admission policy evaluator
  verify_admission_policy.py AI identity/annotation admission verifier
  verify_admission_digest_gate.py admission digest/gate tamper verifier
  verify_admission_audit.py  admission audit fixture verifier
  verify_admission_response.py AdmissionReview response verifier
  verify_admission_server.py local admission HTTP server verifier
  run_admission_kind_smoke.py optional kind admission smoke harness
  verify_release.py            반복 release verification suite
assets/brand/
  kubeactuary-symbol.png       선택된 프로젝트 심볼
  symbol-option-*.svg          이전 심볼 후보
tests/
  test_cli.py                  CLI tests
```

## 개발

현재 CLI는 별도 패키지 설치가 필요 없습니다.

```sh
python3 -B -m unittest discover -s tests
python3 -B scripts/verify_release.py --version 0.2.0
python3 -B scripts/verify_release_taskboard.py
python3 -B scripts/verify_release_progress.py
python3 -B scripts/generate_release_progress.py --format markdown --evidence-dir evidence/live
python3 -B scripts/verify_version_worklist.py
python3 -B scripts/generate_version_worklist.py --format markdown --open-only
python3 -B scripts/generate_version_worklist.py --format markdown --open-only --evidence-dir evidence/live
python3 -B scripts/generate_version_worklist.py --format markdown --open-only --probe-environment
python3 -B scripts/generate_version_worklist.py --format json --version 0.4.3
python3 -B scripts/prepare_version_iteration.py /tmp/kubeactuary-version-iteration --version 0.4.3
python3 -B scripts/prepare_version_iteration.py /tmp/kubeactuary-version-iteration --open-only --evidence-dir evidence/live
python3 -B scripts/compare_version_iterations.py /tmp/kubeactuary-before /tmp/kubeactuary-after --format markdown
python3 -B scripts/record_version_iteration.py /tmp/kubeactuary-version-history --open-only --probe-environment
python3 -B scripts/record_version_iteration.py /tmp/kubeactuary-version-history --open-only --evidence-dir evidence/live
python3 -B scripts/inspect_version_history.py /tmp/kubeactuary-version-history
python3 -B scripts/select_next_version_task.py --version 0.4.3
python3 -B scripts/select_next_version_task.py --evidence-dir evidence/live
python3 -B scripts/select_next_version_task.py --evidence-dir evidence/live --skip-complete-evidence
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --skip-complete-evidence
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --probe-environment
python3 -B scripts/run_next_version_task.py evidence/live
python3 -B scripts/run_next_version_task.py evidence/live --run
python3 -B scripts/run_next_version_task.py evidence/live --run --record
python3 -B scripts/advance_version_iteration.py evidence/live /tmp/kubeactuary-version-history
python3 -B scripts/advance_version_iteration.py evidence/live /tmp/kubeactuary-version-history --run
python3 -B scripts/advance_version_iteration.py evidence/live /tmp/kubeactuary-version-history --probe-environment
python3 -B scripts/verify_external_gate_plan.py
python3 -B scripts/verify_external_gate_command_safety.py
python3 -B scripts/verify_external_gate_evidence.py
python3 -B scripts/verify_external_evidence_builder.py
python3 -B scripts/verify_external_evidence_bundle.py
python3 -B scripts/verify_release_evidence_directory.py
python3 -B scripts/verify_release_evidence_status.py
python3 -B scripts/verify_clean_artifacts.py
python3 -B bin/kube-actuary doctor
python3 -B scripts/verify_crd_compatibility.py
python3 -B scripts/verify_crd_explain_quality.py
python3 -B scripts/verify_conformance_suite.py
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
python3 -B scripts/verify_live_validation_readiness.py --probe-environment
python3 -B scripts/generate_live_validation_queue.py --format markdown --probe-environment
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
```

선택된 next-task runner는 준비된 task가 `tool-ready`가 아니면
`blocked-by-environment` 또는 `missing-tools`를 zero-run 상태로 기록하고,
evidence 디렉터리를 갱신하기 전에는 live capture 명령을 재시도하지 않습니다.

예제 검증:

```sh
python3 -B bin/kube-actuary validate examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/apply-configmap.preflight.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_file(path) }; puts "yaml ok"' .github/workflows/ci.yml charts/kubeactuary/Chart.yaml charts/kubeactuary/values.yaml deploy/kustomize/base/kustomization.yaml deploy/kustomize/overlays/controller-namespace/kustomization.yaml deploy/kustomize/overlays/controller-cluster/kustomization.yaml deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml deploy/controller/namespace-scoped-rbac.yaml deploy/controller/cluster-scoped-rbac.yaml deploy/admission/validatingwebhookconfiguration.yaml
```

## 브랜드 후보

심볼 후보는 [docs/brand-options.md](docs/brand-options.md)에 있습니다.

추천 방향은 cloud-native 느낌을 유지하되, Kubernetes operation ring, proof
check, risk signal을 함께 담은 절제된 마크입니다. 최종 로고를 README 헤더에
고정하기 전에 하나를 선택하면 됩니다.

## 로드맵

현재 v0.2.0:

- auth, dry-run, diff, rollback, health-plan evidence collector
- 로컬 capsule 구조 검증
- 로컬 runtime과 kubectl client 진단
- GitHub Actions CI와 release notes dry-run 도구
- versioned agent help compatibility 계약
- deterministic capsule spec digest
- 로컬 evidence workflow를 위한 CRD 렌더링 개선
- 로컬 fixture와 향후 controller 호환성을 위한 CRD status condition mapping
- upstream Kubernetes N/N-1/N-2와 managed-service support note를 위한
  offline CRD compatibility smoke
- offline verification이 포함된 CRD upgrade/rollback fixture
- kubectl explain description과 offline quality check
- 순수 저부하 controller reconcile 모델, watch boundary, read-only sync plan
  계약
- Helm, Kustomize, release archive, Krew manifest 검증 경로

이후:

- 저부하 controller
- CRD status condition mapping
- agent workflow examples
- real Krew install validation
- AI-originated write용 optional admission webhook
- agent help contract versioning

자세한 내용은 [docs/roadmap.md](docs/roadmap.md)를 참고하세요.

## 상태

v0.2.0 alpha. local-first evidence collector workflow와 specification seed로는
사용할 수 있지만, 아직 production controller는 아닙니다.

## 라이선스

MIT. [LICENSE](LICENSE)를 참고하세요.

기여 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md), attribution 상태는
[NOTICE](NOTICE)를 참고하세요.
