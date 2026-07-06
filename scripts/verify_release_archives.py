#!/usr/bin/env python3
"""Verify release archive generation and install smoke."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGER = ROOT / "scripts" / "package_release_archives.py"
VERSION = (ROOT / "VERSION").read_text().strip()
TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")
REQUIRED_MEMBERS = (
    "VERSION",
    "LICENSE",
    "README.md",
    "README.ko.md",
    "bin/kube-actuary",
    "bin/kubectl-actuary",
    "bin/kube-actuary-controller",
    "controller/__init__.py",
    "controller/reconcile.py",
    "controller/runtime.py",
    "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
    "schemas/operation-capsule.v0alpha1.schema.json",
)


def run_python(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def verify_sha256(archive: Path, errors: list[str]) -> None:
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    if not sidecar.is_file():
        errors.append(f"missing sha256 sidecar: {sidecar.name}")
        return
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if sidecar.read_text().strip() != f"{digest}  {archive.name}":
        errors.append(f"sha256 sidecar mismatch: {archive.name}")


def verify_members(archive: Path, target: str, errors: list[str]) -> None:
    root = f"kube-actuary-{VERSION}-{target}"
    with tarfile.open(archive, "r:gz") as tar:
        names = set(tar.getnames())
        for required in REQUIRED_MEMBERS:
            member = f"{root}/{required}"
            if member not in names:
                errors.append(f"{archive.name} missing {required}")
        for member in tar.getmembers():
            if member.name.endswith(("kube-actuary", "kubectl-actuary", "kube-actuary-controller")):
                if member.mode & 0o111 == 0:
                    errors.append(f"{archive.name} member is not executable: {member.name}")


def install_smoke(archive: Path, target: str, tmpdir: Path, errors: list[str]) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(tmpdir)
    root = tmpdir / f"kube-actuary-{VERSION}-{target}"
    checks = (
        (root / "bin" / "kube-actuary", "--version", "kube-actuary 0.2.0"),
        (root / "bin" / "kubectl-actuary", "--version", "kube-actuary 0.2.0"),
        (root / "bin" / "kube-actuary-controller", "health", '"status": "ok"'),
    )
    for path, arg, expected in checks:
        result = subprocess.run(
            [sys.executable, "-B", str(path), arg],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0 or expected not in result.stdout:
            errors.append(f"install smoke failed for {path.name}: {result.stderr.strip() or result.stdout.strip()}")


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "dist"
        result = run_python(PACKAGER, "--version", VERSION, "--output-dir", str(output_dir))
        if result.returncode != 0:
            print("release-archives: failed")
            print(result.stderr.strip())
            return 1
        for target in TARGETS:
            archive = output_dir / f"kube-actuary-{VERSION}-{target}.tar.gz"
            if not archive.is_file():
                errors.append(f"missing archive: {archive.name}")
                continue
            verify_sha256(archive, errors)
            verify_members(archive, target, errors)
        install_smoke(output_dir / f"kube-actuary-{VERSION}-linux-amd64.tar.gz", "linux-amd64", Path(tmp), errors)

    if errors:
        print("release-archives: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-archives: passed")
    print("targets: linux-amd64, linux-arm64, darwin-amd64, darwin-arm64")
    print("sha256: verified")
    print("install-smoke: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
