#!/usr/bin/env python3
"""Generate an air-gapped install manifest for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")
REPO_ARTIFACTS = (
    "charts/kubeactuary",
    "deploy/kustomize",
    "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
    "deploy/controller/namespace-scoped-rbac.yaml",
    "deploy/controller/cluster-scoped-rbac.yaml",
    "docs/release-archives.md",
    "docs/krew.md",
    "docs/supply-chain.md",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def expected_files(version: str) -> tuple[str, ...]:
    archives = tuple(f"kube-actuary-{version}-{target}.tar.gz" for target in TARGETS)
    sidecars = tuple(f"{archive}.sha256" for archive in archives)
    return (
        *archives,
        *sidecars,
        f"kube-actuary-{version}.sbom.json",
        f"kube-actuary-{version}.provenance.json",
        "actuary.yaml",
    )


def generate_manifest(version: str, artifact_dir: Path) -> dict[str, Any]:
    artifacts = [artifact(artifact_dir / name) for name in expected_files(version)]
    return {
        "schemaVersion": "kube-actuary.airgap.v1",
        "name": "kube-actuary",
        "version": version,
        "requiredReleaseArtifacts": artifacts,
        "requiredRepositoryArtifacts": list(REPO_ARTIFACTS),
        "offlineChecks": [
            "python3 -B scripts/verify_release_archives.py",
            "python3 -B scripts/verify_krew_manifest.py",
            "python3 -B scripts/verify_supply_chain.py",
            "python3 -B scripts/verify_airgap_bundle.py",
        ],
        "installNotes": [
            "Install release archives from local files only.",
            "Use charts/kubeactuary or deploy/kustomize from the checked-out repository.",
            "Verify every SHA-256 before copying artifacts across trust boundaries.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate air-gapped install manifest.")
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)

    text = json.dumps(generate_manifest(args.version, Path(args.artifact_dir)), indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
