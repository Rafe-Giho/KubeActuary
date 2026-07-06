# Security Policy

KubeActuary is an alpha evidence and gate workflow for Kubernetes operations.
It is not a privileged executor and should not be treated as a complete
security boundary.

## Supported Versions

Until v1.0.0, security fixes target:

- `main`
- the most recent tagged alpha release, when a tag exists

Older alpha tags may receive documentation-only mitigation notes instead of
backported patches.

## Reporting a Vulnerability

Use GitHub private vulnerability reporting or a GitHub security advisory when
available for this repository. Do not open a public issue with exploit details,
cluster credentials, kubeconfigs, tokens, or customer data.

Include:

- affected KubeActuary version or commit;
- whether the issue affects CLI, CRD rendering, MCP wrapper, admission
  prototype, packaging, or docs;
- minimal reproduction steps using redacted example manifests or capsules;
- expected impact and any known mitigation.

Expected handling:

- acknowledge within 7 days when the project is actively maintained;
- triage severity and affected surfaces;
- publish a fix, mitigation, or documented non-issue before public details are
  discussed.

## Security Boundaries

KubeActuary should:

- avoid direct Kubernetes write execution;
- keep safe collectors auditable and low-overhead;
- make `execute_approved_capsule` unavailable by default;
- keep optional admission webhook behavior opt-in and failure-tolerant.

KubeActuary does not replace Kubernetes RBAC, policy engines, GitOps approval,
image scanning, runtime security, or incident response.
