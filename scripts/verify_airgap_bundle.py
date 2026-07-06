#!/usr/bin/env python3
"""Verify air-gapped bundle manifest generation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
PACKAGER = ROOT / "scripts" / "package_release_archives.py"
SBOM = ROOT / "scripts" / "generate_sbom.py"
PROVENANCE = ROOT / "scripts" / "generate_provenance.py"
KREW = ROOT / "scripts" / "generate_krew_manifest.py"
AIRGAP = ROOT / "scripts" / "generate_airgap_manifest.py"
DOC = ROOT / "docs" / "air-gapped-install.md"
TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")


def run_python(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_output(path: Path, output: str) -> None:
    path.write_text(output)


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "dist"
        package = run_python(PACKAGER, "--version", VERSION, "--output-dir", str(output_dir))
        if package.returncode != 0:
            errors.append(f"archive packaging failed: {package.stderr.strip()}")

        sbom = run_python(SBOM, "--version", VERSION)
        if sbom.returncode != 0:
            errors.append(f"SBOM generation failed: {sbom.stderr.strip()}")
        else:
            write_output(output_dir / f"kube-actuary-{VERSION}.sbom.json", sbom.stdout)

        provenance = run_python(PROVENANCE, "--version", VERSION, "--artifact-dir", str(output_dir))
        if provenance.returncode != 0:
            errors.append(f"provenance generation failed: {provenance.stderr.strip()}")
        else:
            write_output(output_dir / f"kube-actuary-{VERSION}.provenance.json", provenance.stdout)

        krew = run_python(KREW, "--version", VERSION, "--archive-dir", str(output_dir), "--output", "-")
        if krew.returncode != 0:
            errors.append(f"Krew manifest generation failed: {krew.stderr.strip()}")
        else:
            write_output(output_dir / "actuary.yaml", krew.stdout)

        manifest_result = run_python(AIRGAP, "--version", VERSION, "--artifact-dir", str(output_dir))
        if manifest_result.returncode != 0:
            errors.append(f"airgap manifest generation failed: {manifest_result.stderr.strip()}")
            manifest = {}
        else:
            manifest = json.loads(manifest_result.stdout)

        if manifest.get("schemaVersion") != "kube-actuary.airgap.v1":
            errors.append("airgap manifest schema mismatch")
        artifacts = {item.get("name"): item for item in manifest.get("requiredReleaseArtifacts", [])}
        expected = []
        for target in TARGETS:
            archive = f"kube-actuary-{VERSION}-{target}.tar.gz"
            expected.extend([archive, f"{archive}.sha256"])
        expected.extend([f"kube-actuary-{VERSION}.sbom.json", f"kube-actuary-{VERSION}.provenance.json", "actuary.yaml"])
        for name in expected:
            path = output_dir / name
            artifact = artifacts.get(name)
            if not artifact:
                errors.append(f"airgap manifest missing artifact: {name}")
                continue
            if artifact.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
                errors.append(f"airgap manifest digest mismatch: {name}")
        repo_artifacts = set(manifest.get("requiredRepositoryArtifacts", []))
        for required in ("charts/kubeactuary", "deploy/kustomize", "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"):
            if required not in repo_artifacts:
                errors.append(f"airgap manifest missing repo artifact: {required}")

    doc = DOC.read_text()
    for required in ("air-gapped", "generate_airgap_manifest.py", "verify_airgap_bundle.py", "SHA-256"):
        if required not in doc:
            errors.append(f"airgap docs missing: {required}")

    if errors:
        print("airgap-bundle: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("airgap-bundle: passed")
    print("release-artifacts: verified")
    print("repo-artifacts: listed")
    print("offline-checklist: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
