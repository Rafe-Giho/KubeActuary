# Kubernetes CLI and AI Operations Landscape

Snapshot date: 2026-07-01.

This is not a claim that every Kubernetes-related repository on the internet was
manually read. The research baseline uses authoritative ecosystem indexes and
representative open-source tools:

- Kubernetes official kubectl plugin model:
  https://kubernetes.io/docs/tasks/extend-kubectl/kubectl-plugins/
- Krew official plugin index:
  https://github.com/kubernetes-sigs/krew-index
- CNCF Landscape:
  https://github.com/cncf/landscape
- Major AI/Kubernetes repos and adjacent operational tools listed below.

## Measured Ecosystem

Local snapshot checks:

- Krew official index: 382 kubectl plugins.
- CNCF Landscape `landscape.yml`: 2,415 entries.

Krew category scan from plugin names and short descriptions:

| Area | Count | What already exists |
| --- | ---: | --- |
| Cost, capacity, resources | 109 | `top`, GPU, VPA, node, quota, usage, requests/limits helpers |
| Context, config, UX | 76 | kubeconfig cleanup, namespace switching, tree/graph/color UX |
| Multi-cluster and edge | 72 | context fanout, federation, snapshots, cluster-specific helpers |
| Debug, logs, trace | 63 | logs, exec, eBPF, tcpdump, support bundles, failed-pod triage |
| RBAC, security, policy | 44 | RBAC maps, access matrices, image scans, PSP/policy helpers |
| AI and natural-language query | 41 | `kubectl ai`, natural-language/query-like interfaces, copilots |
| Network and service mesh | 29 | port-forward, reachability, ingress, Cilium, mesh helpers |
| GitOps and delivery | 20 | Argo helpers, diff/apply tools, Helm/Kustomize support |
| Storage and data | 19 | PVC/PV, Ceph/Rook, mounts, backups, snapshots |

The counts are heuristic because many plugins span several categories.

## Representative Existing Tools

### Natural-language and agent interfaces

- `kubectl-ai`: AI-powered Kubernetes assistant that translates user intent into
  Kubernetes operations. It supports multiple LLM providers, local models,
  interactive use, and MCP client/server modes.
  https://github.com/GoogleCloudPlatform/kubectl-ai
- `k8sgpt`: cluster analyzer with explainable findings, built-in analyzers, AI
  backends, and MCP support.
  https://github.com/k8sgpt-ai/k8sgpt
- `kagent`: CNCF sandbox project for Kubernetes-native AI agents. Agents, tools,
  and model configs are represented as Kubernetes custom resources.
  https://github.com/kagent-dev/kagent
- `kubectl-mcp-server`: MCP server exposing many Kubernetes management tools to
  AI clients.
  https://github.com/rohitg00/kubectl-mcp-server
- `mcp-server-kubernetes`: Node-based MCP server for Kubernetes management.
  https://github.com/Flux159/mcp-server-kubernetes
- `MKP`: Go MCP server for listing and applying Kubernetes resources.
  https://github.com/StacklokLabs/mkp

### Static analysis, policy, and readiness

- `kube-score`: static analysis for Kubernetes objects with reliability and
  security recommendations.
  https://github.com/zegl/kube-score
- `kube-linter`: static analysis for YAML, Helm, and Kustomize with production
  readiness and security best practices.
  https://github.com/stackrox/kube-linter
- `Polaris`: validates best practices in live Kubernetes clusters.
  https://github.com/FairwindsOps/polaris
- `Pluto`: finds deprecated Kubernetes API versions in repositories and Helm
  releases.
  https://github.com/FairwindsOps/pluto
- `Kyverno`: Kubernetes-native policy engine.
  https://kyverno.io/
- `Open Policy Agent`: general policy engine widely used in cloud-native
  systems.
  https://www.openpolicyagent.org/

### Delivery and operations

- Argo CD, Flux, Helm, Kustomize, Skaffold, Tilt, and Garden cover GitOps,
  packaging, manifest generation, and local development loops.
- Prometheus, Grafana, Jaeger, OpenTelemetry, Cilium Hubble, Pixie, and related
  projects cover metrics, traces, logs, network visibility, and runtime insight.
- Trivy, Kubescape, Falco, kube-bench, and similar tools cover vulnerability,
  posture, benchmark, and runtime security.

## Observed Gap

The ecosystem has many tools that:

- let humans or AI query clusters,
- translate natural language to actions,
- analyze manifests,
- expose Kubernetes as MCP tools,
- enforce policy,
- reconcile desired state.

The underdeveloped gap is an AI operation contract:

- one artifact per proposed cluster action,
- evidence required before execution,
- blast-radius estimate,
- rollback requirement,
- post-change proof,
- audit trail independent of the LLM,
- usable by humans, MCP clients, GitOps, and CI.

KubeActuary is aimed at that gap.

