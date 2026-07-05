# KubeActuary

<p align="center">
  <img src="assets/brand/kubeactuary-symbol.png" alt="KubeActuary symbol" width="180">
</p>

> AI가 Kubernetes를 조작하기 전에 증거를 들고 오게 만드는 실행 계약 CLI.

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](VERSION)
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

## v0.1.0에서 되는 것

- `kubectl` 명령 또는 manifest 경로에서 로컬 operation capsule 생성
- 대상, 위험도, 상태, 증거 확인
- 수동 증거 첨부
- `kubectl auth can-i` 증거 수집
- 누락/실패 증거 검증
- 실행 게이트 open/closed 판정
- 로컬 캡슐을 Kubernetes `OperationCapsule` CRD 객체로 렌더링
- `kubectl` 플러그인 진입점 제공
- JSON Schema와 CRD seed 제공

v0.1.0에서 하지 않는 것:

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
attach-evidence    수동 증거 첨부
collect auth       kubectl auth can-i 증거 수집
verify             필수 증거 확인
gate               실행 게이트 open/closed 출력
render-crd         캡슐을 Kubernetes CRD 객체로 렌더링
demo               고위험 샘플 캡슐 출력
```

버전 확인:

```sh
python3 bin/kube-actuary --version
```

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
  kubectl-actuary              kubectl plugin entrypoint
deploy/crds/
  operationcapsules...yaml     CRD seed
docs/
  collectors.md                evidence collector 계약
  landscape.md                 생태계 조사
  paradigm.md                  운영 모델
  project-assessment.md        현재 성숙도 평가
  roadmap.md                   개발 계획
  v0.1.0.md                    alpha release 목표
  test-plan-v0.1.0.md          release test plan
  test-results-v0.1.0.md       최신 검증 결과
  crd-design.md                Kubernetes-native 설계
  interoperability.md          CLI, MCP, GitOps, admission 계약
  novelty-check.md             신규성 경계
examples/
  *.capsule.json               로컬 capsule 예제
  operationcapsule-scale.yaml  CRD 예제
schemas/
  operation-capsule...json     JSON Schema
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
```

예제 검증:

```sh
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; YAML.load_file("deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"); puts "yaml ok"'
```

## 브랜드 후보

심볼 후보는 [docs/brand-options.md](docs/brand-options.md)에 있습니다.

추천 방향은 cloud-native 느낌을 유지하되, Kubernetes operation ring, proof
check, risk signal을 함께 담은 절제된 마크입니다. 최종 로고를 README 헤더에
고정하기 전에 하나를 선택하면 됩니다.

## 로드맵

가까운 작업:

- `collect dry-run`: server-side dry-run 증거
- `collect diff`: `kubectl diff` 증거
- rollback evidence helper
- capsule digest/signature
- CRD status condition mapping

이후:

- 저부하 controller
- optional MCP server
- Krew packaging
- AI-originated write용 optional admission webhook
- Kyverno, OPA, kube-linter, kube-score, Pluto adapter

자세한 내용은 [docs/roadmap.md](docs/roadmap.md)를 참고하세요.

## 상태

v0.1.0 alpha. local-first evidence workflow와 specification seed로는 사용할 수
있지만, 아직 production controller는 아닙니다.

## 라이선스

MIT. [LICENSE](LICENSE)를 참고하세요.
