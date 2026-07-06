#!/usr/bin/env python3
"""Generate a Krew manifest from release archives."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ("linux-amd64", "linux", "amd64"),
    ("linux-arm64", "linux", "arm64"),
    ("darwin-amd64", "darwin", "amd64"),
    ("darwin-arm64", "darwin", "arm64"),
)


def archive_digest(archive: Path) -> str:
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def platform_entry(version: str, target: str, os_name: str, arch: str, base_uri: str, archive_dir: Path) -> str:
    archive_name = f"kube-actuary-{version}-{target}.tar.gz"
    archive = archive_dir / archive_name
    digest = archive_digest(archive)
    root = f"kube-actuary-{version}-{target}"
    return f"""  - selector:
      matchLabels:
        os: {os_name}
        arch: {arch}
    uri: {base_uri.rstrip("/")}/{archive_name}
    sha256: {digest}
    bin: kubectl-actuary
    files:
      - from: {root}/bin/kubectl-actuary
        to: .
      - from: {root}/bin/kube-actuary
        to: .
"""


def manifest(version: str, archive_dir: Path, base_uri: str) -> str:
    entries = "".join(platform_entry(version, target, os_name, arch, base_uri, archive_dir) for target, os_name, arch in TARGETS)
    return f"""apiVersion: krew.googlecontainertools.github.com/v1alpha2
kind: Plugin
metadata:
  name: actuary
spec:
  version: v{version}
  homepage: https://github.com/choo-o/kubeactuary
  shortDescription: Evidence gates for AI-assisted Kubernetes operations.
  description: |
    KubeActuary records proposed Kubernetes operations as evidence-carrying
    capsules. The kubectl plugin drafts, inspects, verifies, and gates capsules
    without executing proposed cluster writes by default.
  platforms:
{entries}"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Krew manifest for kubectl-actuary.")
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    parser.add_argument("--archive-dir", required=True)
    parser.add_argument("--base-uri", default=None)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)

    base_uri = args.base_uri or f"https://github.com/choo-o/kubeactuary/releases/download/v{args.version}"
    text = manifest(args.version, Path(args.archive_dir), base_uri)
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
