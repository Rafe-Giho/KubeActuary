#!/usr/bin/env python3
"""Verify generated Krew manifest contract without requiring Krew."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGER = ROOT / "scripts" / "package_release_archives.py"
GENERATOR = ROOT / "scripts" / "generate_krew_manifest.py"
DOC = ROOT / "docs" / "krew.md"
VERSION = (ROOT / "VERSION").read_text().strip()
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


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "dist"
        package = run_python(PACKAGER, "--version", VERSION, "--output-dir", str(output_dir))
        if package.returncode != 0:
            errors.append(f"archive packaging failed: {package.stderr.strip()}")
        manifest = run_python(
            GENERATOR,
            "--version",
            VERSION,
            "--archive-dir",
            str(output_dir),
            "--base-uri",
            f"https://example.invalid/kubeactuary/v{VERSION}",
        )
        text = manifest.stdout
        if manifest.returncode != 0:
            errors.append(f"manifest generation failed: {manifest.stderr.strip()}")

        for required in (
            "apiVersion: krew.googlecontainertools.github.com/v1alpha2",
            "kind: Plugin",
            "name: actuary",
            f"version: v{VERSION}",
            "bin: kubectl-actuary",
            "from: kube-actuary-",
            "to: .",
            "os: linux",
            "os: darwin",
            "arch: amd64",
            "arch: arm64",
        ):
            if required not in text:
                errors.append(f"Krew manifest missing: {required}")

        for target in TARGETS:
            archive_name = f"kube-actuary-{VERSION}-{target}.tar.gz"
            archive = output_dir / archive_name
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            if archive_name not in text:
                errors.append(f"Krew manifest missing archive uri: {archive_name}")
            if digest not in text:
                errors.append(f"Krew manifest missing archive digest: {target}")
            if not re.search(rf"from: kube-actuary-{re.escape(VERSION)}-{target}/bin/kubectl-actuary", text):
                errors.append(f"Krew manifest missing plugin mapping: {target}")
            if not re.search(rf"from: kube-actuary-{re.escape(VERSION)}-{target}/bin/kube-actuary", text):
                errors.append(f"Krew manifest missing helper mapping: {target}")

    doc = DOC.read_text()
    for required in ("Krew", "generate_krew_manifest.py", "kubectl-actuary", "kubectl krew"):
        if required not in doc:
            errors.append(f"Krew docs missing: {required}")

    if errors:
        print("krew-manifest: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("krew-manifest: passed")
    print("plugin: actuary")
    print("platforms: linux-amd64, linux-arm64, darwin-amd64, darwin-arm64")
    print("mode: offline-generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
