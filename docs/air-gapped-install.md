# Air-Gapped Install

This runbook defines the offline artifact checklist for installing KubeActuary
without network access.

## Prepare Artifacts

On a connected machine:

```sh
python3 -B scripts/package_release_archives.py --version 0.2.0 --output-dir dist
python3 -B scripts/generate_sbom.py --version 0.2.0 --output dist/kube-actuary-0.2.0.sbom.json
python3 -B scripts/generate_provenance.py --version 0.2.0 --artifact-dir dist --output dist/kube-actuary-0.2.0.provenance.json
python3 -B scripts/generate_krew_manifest.py --version 0.2.0 --archive-dir dist --output dist/actuary.yaml
python3 -B scripts/generate_airgap_manifest.py --version 0.2.0 --artifact-dir dist --output dist/kube-actuary-0.2.0.airgap.json
```

## Required Release Artifacts

- release archives for `linux-amd64`, `linux-arm64`, `darwin-amd64`, and
  `darwin-arm64`
- `.sha256` sidecars for every archive
- CycloneDX SBOM
- provenance JSON
- Krew manifest
- air-gapped manifest

## Required Repository Artifacts

- `charts/kubeactuary`
- `deploy/kustomize`
- `deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml`
- `deploy/controller/namespace-scoped-rbac.yaml`
- `deploy/controller/cluster-scoped-rbac.yaml`

## Offline Checks

Before moving artifacts across trust boundaries, verify every SHA-256 listed in
the air-gapped manifest. On the connected machine, run:

```sh
python3 -B scripts/verify_airgap_bundle.py
```

Inside the disconnected environment, use local files only:

```sh
python3 bin/kube-actuary --version
kubectl kustomize deploy/kustomize/base
kubectl kustomize deploy/kustomize/overlays/controller-namespace
```

Do not fetch Helm charts, Krew indexes, container images, or remote manifests as
part of the offline install.
