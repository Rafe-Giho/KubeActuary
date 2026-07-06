# Threat Model

KubeActuary reduces risk around AI-assisted Kubernetes operations by separating
intent, evidence, gate decision, and external execution.

## Assets

- OperationCapsule spec and required evidence contract;
- capsule digest and rendered CRD annotations;
- evidence records and source hashes;
- MCP safe-tool surface;
- optional admission annotations and audit records;
- release artifacts, checksums, SBOM, and provenance.

## Trust Boundaries

- AI agent to KubeActuary CLI or MCP wrapper;
- local capsule files to Git or CI artifacts;
- KubeActuary CRD objects to Kubernetes controllers;
- optional admission webhook to Kubernetes API server;
- human/GitOps executor to actual Kubernetes writes.

## In Scope

- accidental or malicious agent attempts to execute writes directly;
- missing, failed, or tampered required evidence;
- capsule digest tampering;
- unsafe expansion of MCP tools;
- optional admission annotation tampering;
- packaging integrity regression.

## Out of Scope

- compromise of Kubernetes API server or etcd;
- stolen kubeconfigs or cloud credentials;
- malicious cluster administrators;
- image vulnerabilities in workloads;
- runtime detection, forensics, and workload isolation.

## Mitigations

- `gate` opens only when required evidence is attached and successful;
- digest excludes `status.evidence` order but covers operation intent;
- `verify_execute_disabled.py` proves execute surfaces are absent or disabled;
- adapter contract checks normalize evidence shape and severity;
- admission fixtures reject missing annotations, digest mismatch, and closed
  gates;
- release verification checks archives, Krew manifests, SBOM, provenance, and
  air-gapped bundle metadata.

## Residual Risk

- alpha CRD/controller/admission contracts may change before v1.0.0;
- live cluster and managed-provider smoke evidence is not present unless
  explicitly attached;
- optional admission uses `failurePolicy: Ignore` by default to avoid cluster
  outages, so it is a guardrail rather than a hard enforcement layer.
