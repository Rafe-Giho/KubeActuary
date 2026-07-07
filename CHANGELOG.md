# Changelog

## 0.9.5 - Pre-GA

Public CLI release scope:

- promote the repository to `0.9.5` as a pre-GA, local-complete CLI release;
- keep the default workflow local-first, auditable, and free of direct
  Kubernetes write execution;
- expose the `kube-actuary` CLI and `kubectl actuary` plugin entrypoint;
- support `OperationCapsule` drafting, inspection, validation, evidence
  attachment, verification, gate decisions, CRD rendering, and deterministic
  spec digests;
- support evidence collectors for auth checks, manifest server-side dry-run,
  manifest diff, explicit rollback basis, and post-change health plans;
- include JSON Schema, CRD seed, example capsules, manifest preflight examples,
  Helm chart seed, Kustomize assets, optional deployment manifests, and the
  low-overhead controller reconcile model;
- publish agent-readable CLI help through
  `python3 -B bin/kube-actuary help agents --format json`;
- align CI with the public test contract:
  `python3 -B -m unittest discover -s tests`;
- keep local helper scripts out of the tracked public release surface.

Still required before a 1.0.0 GA claim:

- green public GitHub Actions run on the pushed repository;
- approved live Kubernetes evidence for cluster smoke, install, and
  resource-budget checks;
- managed-provider evidence where support is claimed;
- final release packaging and distribution evidence.

## 0.1.0

Initial alpha scope:

- local `OperationCapsule` JSON workflow;
- `draft`, `inspect`, `attach-evidence`, `collect auth`, `verify`, `gate`,
  `render-crd`, and `demo` commands;
- kubectl plugin entrypoint;
- JSON Schema;
- CRD seed;
- examples.
