#!/usr/bin/env python3
"""Verify SBOM and provenance generation."""

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
DOC = ROOT / "docs" / "supply-chain.md"
TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")


def run_python(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_json_command(errors: list[str], path: Path, *args: str) -> dict:
    result = run_python(path, *args)
    if result.returncode != 0:
        errors.append(f"{path.name} failed: {result.stderr.strip()}")
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} did not emit JSON: {exc}")
        return {}


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "dist"
        package = run_python(PACKAGER, "--version", VERSION, "--output-dir", str(output_dir))
        if package.returncode != 0:
            errors.append(f"archive packaging failed: {package.stderr.strip()}")

        sbom = load_json_command(errors, SBOM, "--version", VERSION)
        provenance = load_json_command(errors, PROVENANCE, "--version", VERSION, "--artifact-dir", str(output_dir))

        if sbom.get("bomFormat") != "CycloneDX":
            errors.append("SBOM must use CycloneDX")
        if sbom.get("specVersion") != "1.5":
            errors.append("SBOM must use CycloneDX 1.5")
        component = sbom.get("metadata", {}).get("component", {})
        if component.get("name") != "kube-actuary" or component.get("version") != VERSION:
            errors.append("SBOM metadata component mismatch")
        components = sbom.get("components", [])
        names = {item.get("name") for item in components}
        for required in ("bin/kube-actuary", "bin/kubectl-actuary", "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"):
            if required not in names:
                errors.append(f"SBOM missing component: {required}")
        for item in components:
            hashes = item.get("hashes", [])
            if not hashes or hashes[0].get("alg") != "SHA-256" or len(hashes[0].get("content", "")) != 64:
                errors.append(f"SBOM component has invalid SHA-256: {item.get('name')}")
                break

        if provenance.get("_type") != "https://in-toto.io/Statement/v1":
            errors.append("provenance must be an in-toto statement")
        if provenance.get("predicateType") != "https://slsa.dev/provenance/v1":
            errors.append("provenance must use SLSA provenance v1 predicate")
        subjects = provenance.get("subject", [])
        if len(subjects) != len(TARGETS):
            errors.append("provenance subject count mismatch")
        for target in TARGETS:
            archive = output_dir / f"kube-actuary-{VERSION}-{target}.tar.gz"
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            subject = next((item for item in subjects if item.get("name") == archive.name), None)
            if not subject:
                errors.append(f"provenance missing subject: {archive.name}")
            elif subject.get("digest", {}).get("sha256") != digest:
                errors.append(f"provenance digest mismatch: {archive.name}")
        build_type = provenance.get("predicate", {}).get("buildDefinition", {}).get("buildType")
        if build_type != "https://github.com/choo-o/kubeactuary/release-archive/v1":
            errors.append("provenance buildType mismatch")

    doc = DOC.read_text()
    for required in ("CycloneDX", "SLSA", "generate_sbom.py", "generate_provenance.py"):
        if required not in doc:
            errors.append(f"supply-chain doc missing: {required}")

    if errors:
        print("supply-chain: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("supply-chain: passed")
    print(f"sbom-components: {len(components)}")
    print(f"provenance-subjects: {len(TARGETS)}")
    print("archive-digests: verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
