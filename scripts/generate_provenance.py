#!/usr/bin/env python3
"""Generate deterministic release-archive provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subjects(version: str, artifact_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for target in TARGETS:
        archive = artifact_dir / f"kube-actuary-{version}-{target}.tar.gz"
        entries.append(
            {
                "name": archive.name,
                "digest": {"sha256": sha256(archive)},
            }
        )
    return entries


def generate_provenance(version: str, artifact_dir: Path) -> dict[str, Any]:
    subject_entries = subjects(version, artifact_dir)
    invocation_seed = json.dumps(subject_entries, sort_keys=True).encode("utf-8")
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": subject_entries,
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/choo-o/kubeactuary/release-archive/v1",
                "externalParameters": {
                    "version": version,
                    "targets": list(TARGETS),
                },
                "internalParameters": {
                    "packager": "scripts/package_release_archives.py",
                    "runtime": "python3-stdlib",
                },
                "resolvedDependencies": [
                    {
                        "uri": "git+https://github.com/choo-o/kubeactuary",
                        "digest": {"sha1": "local-worktree"},
                    }
                ],
            },
            "runDetails": {
                "builder": {"id": "kube-actuary-local-stdlib"},
                "metadata": {
                    "invocationId": hashlib.sha256(invocation_seed).hexdigest(),
                },
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate release archive provenance.")
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)

    text = json.dumps(generate_provenance(args.version, Path(args.artifact_dir)), indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
