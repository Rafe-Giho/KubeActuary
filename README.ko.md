# KubeActuary

> AI-assisted Kubernetes를 위한 evidence-carrying operations CLI.

[![Version](https://img.shields.io/badge/version-0.9.5-blue)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB)](bin/kube-actuary)
[![Kubernetes](https://img.shields.io/badge/kubernetes-OperationCapsule-326CE5)](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)

[English](README.md) | 한국어

KubeActuary는 제안된 Kubernetes 작업을 감사 가능한 `OperationCapsule`로
바꾸는 local-first CLI입니다. 캡슐에는 작업 의도, 대상, 제안된 명령 또는
manifest, 위험도, 필요한 증거, 수집된 증거, rollback 근거, 사후 확인 계획,
gate 판정이 함께 기록됩니다.

이 도구는 AI-assisted Kubernetes workflow를 위해 설계됐지만, AI가 `kubectl`
명령을 만들 수 있다는 이유만으로 그 명령을 신뢰하지 않습니다. KubeActuary는
제안, 증거, 승인, 실행을 분리합니다. 기본 CLI 경로는 증거를 수집하고
검증하며, 직접적인 클러스터 write를 실행하지 않습니다.

## 왜 필요한가

AI와 자동화 도구는 이미 Kubernetes 작업을 생성할 수 있습니다. 부족한 것은
무언가를 실제로 바꾸기 전에 그 작업이 충분한 증거를 갖췄는지 판단하는 작고
이식 가능한 계약입니다.

KubeActuary가 제공하는 계약은 다음과 같습니다.

- 작업 의도를 구조화된 파일로 기록
- 대상 범위와 기본 위험도 식별
- authorization, server dry-run, diff, rollback, health-plan 증거 수집
- 작업 spec에 대한 deterministic digest 제공
- 필수 증거가 있고 성공했을 때만 gate open
- 같은 로컬 캡슐을 Kubernetes `OperationCapsule` 리소스로 렌더링

## 현재 릴리스

v0.9.5는 pre-GA, local-complete CLI 릴리스입니다. 공개 저장소 범위를
기준으로 CLI, capsule schema, CRD seed, manifest preflight collector, 명시적
rollback과 health-plan evidence, deterministic digest, offline verification,
example capsule, 저부하 controller design이 체크인된 트리에서 테스트 가능한
상태입니다.

하지만 v0.9.5는 아직 1.0.0 production claim이 아닙니다. 1.0.0까지 남은
작업은 승인된 Kubernetes와 provider 환경에서 live evidence를 캡처하는
것입니다. 여기에는 cluster smoke run, installation proof, managed-provider
check, public CI evidence, resource-budget evidence가 포함됩니다. 필요한
도구나 네트워크 접근이 없는 환경에서는 이 항목들이 의도적으로 blocked
상태로 남습니다.

포함된 것:

- 로컬 CLI와 `kubectl` plugin entrypoint
- JSON `OperationCapsule` 형식과 schema
- Kubernetes `OperationCapsule` CRD seed
- manifest preflight용 server-side dry-run, diff collector
- 명시적인 rollback과 health-plan evidence
- deterministic digest 출력
- offline validation, verification, gate decision
- status-only 경계를 가진 저부하 controller reconcile model
- Helm chart seed, Kustomize asset, optional deployment manifest
- optional admission manifest prototype
- 안전한 tool integration을 위한 agent-readable help

기본 경로에서 의도적으로 하지 않는 것:

- no direct cluster write execution;
- in-cluster LLM 없음
- cluster-wide scan 없음
- controller 필수 아님
- admission webhook 필수 아님
- 외부 Python 패키지 의존성 없음

릴리스 경계:

- `0.9.5`: local implementation과 offline contract가 존재하는 상태
- `1.0.0`: external live evidence와 public CI green이 완료되어야 GA claim 가능

## 설치

저장소를 clone하고 Python으로 CLI를 실행합니다.

```sh
git clone https://github.com/Rafe-Giho/KubeActuary.git
cd KubeActuary
python3 bin/kube-actuary --version
```

`bin/`을 `PATH`에 넣으면 `kubectl` plugin으로 사용할 수 있습니다.

```sh
export PATH="$PWD/bin:$PATH"
kubectl actuary --version
```

현재 CLI는 별도 Python 패키지 설치가 필요 없습니다.

## 빠른 시작

포함된 read-only 예제를 검증하고 gate를 확인합니다.

```sh
python3 bin/kube-actuary verify examples/read-pods.verified.capsule.json
python3 bin/kube-actuary gate examples/read-pods.verified.capsule.json
```

예상 gate 결과:

```text
gate: open
id: opcap-example-read-pods
risk: low
command: kubectl get pods -n default
```

더 위험한 제안을 draft로 만듭니다. 아래 명령은 제안된 작업을 기록할 뿐,
내부의 `kubectl scale` 명령을 실행하지 않습니다.

```sh
python3 bin/kube-actuary draft \
  --intent "increase checkout API capacity for expected traffic" \
  --command "kubectl scale deployment checkout-api --replicas=6 -n prod" \
  --actor "ai-agent" \
  --out /tmp/scale.capsule.json
```

캡슐을 확인하고 구조를 검증합니다.

```sh
python3 bin/kube-actuary inspect /tmp/scale.capsule.json
python3 bin/kube-actuary validate /tmp/scale.capsule.json
```

사람의 승인 증거를 첨부합니다.

```sh
python3 bin/kube-actuary attach-evidence /tmp/scale.capsule.json \
  --id owner-approval \
  --summary "checkout service owner approved the scale-up window" \
  --actor "platform-reviewer" \
  --out /tmp/scale.with-approval.json
```

제안된 write를 실행하지 않고 권한 증거를 수집합니다.

```sh
python3 bin/kube-actuary collect auth /tmp/scale.with-approval.json \
  --out /tmp/scale.with-auth.json
```

증거 상태와 gate 판정을 확인합니다.

```sh
python3 bin/kube-actuary verify /tmp/scale.with-auth.json
python3 bin/kube-actuary gate /tmp/scale.with-auth.json
```

## Manifest Preflight

Manifest 기반 작업에서는 Kubernetes preflight evidence를 수집할 수 있습니다.
이 collector들은 설정된 클러스터에 접속할 수 있지만, 변경을 적용하지 않는
evidence-only 작업입니다.

```sh
python3 bin/kube-actuary draft \
  --intent "apply demo config map" \
  --manifest examples/configmap-demo.yaml \
  --actor "ai-agent" \
  --out /tmp/apply.capsule.json

python3 bin/kube-actuary collect dry-run /tmp/apply.capsule.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-dry-run.json

python3 bin/kube-actuary collect diff /tmp/apply.with-dry-run.json \
  --manifest examples/configmap-demo.yaml \
  --out /tmp/apply.with-diff.json

python3 bin/kube-actuary collect rollback /tmp/apply.with-diff.json \
  --manifest examples/configmap-demo.rollback.yaml \
  --out /tmp/apply.with-rollback.json

python3 bin/kube-actuary collect health-plan /tmp/apply.with-rollback.json \
  --out /tmp/apply.ready.json
```

`collect dry-run`은 `kubectl apply --dry-run=server`를 사용합니다.
`collect diff`는 `kubectl diff`를 사용합니다. 둘 다 변경을 적용하지 않고
캡슐에 증거만 첨부합니다.

## OperationCapsule

`OperationCapsule`은 KubeActuary의 핵심 기록입니다.

| Section | 목적 |
| --- | --- |
| `metadata` | 캡슐 id, 생성 시간, actor 정보 |
| `spec.intent` | 작업이 필요한 이유 |
| `spec.proposedCommand` 또는 `spec.manifest` | 제안된 작업 |
| `spec.target` | Kubernetes verb, resource, namespace, scope |
| `spec.risk` | 기본 위험도와 blast-radius 분류 |
| `spec.requiredEvidence` | gate를 열기 전에 필요한 증거 |
| `status.evidence` | 첨부된 증거와 collector 결과 |
| `status.gate` | open/closed 판정과 이유 |

`digest` 명령은 status evidence를 제외하고 operation spec을 해시합니다. 따라서
같은 작업 의도는 증거가 추가되더라도 같은 digest를 유지합니다.

```sh
python3 bin/kube-actuary digest examples/apply-configmap.preflight.capsule.json
```

## 명령

| 명령 | 목적 |
| --- | --- |
| `draft` | 의도와 명령 또는 manifest에서 operation capsule 생성 |
| `inspect` | 대상, 위험도, 상태, 증거 요약 |
| `validate` | capsule JSON 구조 검증 |
| `doctor` | 로컬 runtime과 `kubectl` client 진단 |
| `attach-evidence` | 수동 증거 첨부 |
| `collect auth` | `kubectl auth can-i` 증거 수집 |
| `collect dry-run` | server-side dry-run 증거 첨부 |
| `collect diff` | `kubectl diff` 증거 첨부 |
| `collect rollback` | 명시적인 rollback 명령 또는 manifest 증거 첨부 |
| `collect health-plan` | 사후 확인 계획 증거 첨부 |
| `digest` | deterministic capsule spec digest 출력 |
| `verify` | 필수 증거 확인 |
| `gate` | gate open/closed 판정 출력 |
| `render-crd` | 로컬 캡슐을 Kubernetes 리소스로 렌더링 |
| `demo` | 고위험 샘플 캡슐 출력 |
| `help` | workflow, safety, evidence, agent 안내 출력 |

Integration을 위한 agent-readable help도 제공합니다.

```sh
python3 bin/kube-actuary help agents --format json
```

## Kubernetes-Native 경로

캡슐을 Kubernetes에 저장하려는 팀을 위해 CRD seed와 예제가 포함되어 있습니다.

- [deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml](deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml)
- [examples/operationcapsule-scale.yaml](examples/operationcapsule-scale.yaml)

로컬 캡슐을 Kubernetes 객체로 렌더링합니다.

```sh
python3 bin/kube-actuary render-crd examples/read-pods.verified.capsule.json \
  --name read-pods \
  --namespace default
```

CRD 경로는 낮은 부하를 전제로 합니다. 하나의 namespaced `OperationCapsule`
리소스, embedded evidence, status-friendly field, cluster-wide scan 금지가
기본입니다.

## Safety Model

KubeActuary는 여러 책임을 하나의 agent action으로 합치지 않습니다.

| 책임 | 대표 actor |
| --- | --- |
| 제안 | AI agent, human, CI |
| 증거 수집 | CLI, CI, policy tools |
| 승인 | human owner 또는 platform reviewer |
| gate 판정 | KubeActuary verification |
| 실행 | human, GitOps, future bounded executor |

Gate는 실행 여부를 나누는 경계입니다. Gate가 closed이면 필수 증거가 없거나
실패했으므로 작업은 진행되면 안 됩니다.

## 프로젝트 구조

```text
bin/                  CLI와 kubectl plugin entrypoint
charts/               Helm chart seed
controller/           저부하 controller reconcile model
deploy/               CRD, optional controller, admission, Kustomize assets
docs/                 설계 문서, runbook, compatibility, roadmap
examples/             capsule, manifest, CRD, CLI-agent workflow 예제
schemas/              JSON Schema와 API freeze contract
tests/                CLI와 behavior tests
```

## 문서

- [Collectors](docs/collectors.md)
- [CRD design](docs/crd-design.md)
- [Kubernetes compatibility](docs/kubernetes-compatibility.md)
- [Controller design](docs/controller.md)
- [Security policy](SECURITY.md)
- [Threat model](docs/threat-model.md)
- [Roadmap](docs/roadmap.md)

## 개발

Unit test를 실행합니다.

```sh
python3 -B -m unittest discover -s tests
```

기여 규칙과 안전 경계는 [CONTRIBUTING.md](CONTRIBUTING.md)에 정리되어
있습니다. 보안 제보 절차는 [SECURITY.md](SECURITY.md)를 참고하세요.

## License

MIT. 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.
