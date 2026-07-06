#!/usr/bin/env python3
"""Generate a deterministic KubeActuary SBOM using Python stdlib only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INCLUDE_ROOTS = (
    "AGENTS.md",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "README.ko.md",
    "VERSION",
    ".github",
    "bin",
    "charts",
    "controller",
    "deploy",
    "docs",
    "examples",
    "schemas",
    "scripts",
    "tests",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "dist", "build"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return False
    return path.is_file()


def iter_files() -> list[Path]:
    files: list[Path] = []
    for entry in INCLUDE_ROOTS:
        path = ROOT / entry
        if path.is_file() and should_include(path):
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*") if should_include(candidate))
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component(path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    return {
        "type": "file",
        "bom-ref": f"file:{relative}",
        "name": relative,
        "hashes": [{"alg": "SHA-256", "content": sha256(path)}],
    }


def generate_sbom(version: str) -> dict[str, Any]:
    components = [component(path) for path in iter_files()]
    seed = json.dumps([item["hashes"][0]["content"] for item in components], sort_keys=True).encode("utf-8")
    serial = hashlib.sha256(seed).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial[:8]}-{serial[8:12]}-{serial[12:16]}-{serial[16:20]}-{serial[20:32]}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "kube-actuary",
                "version": version,
            },
            "tools": [
                {
                    "vendor": "KubeActuary",
                    "name": "generate_sbom.py",
                    "version": version,
                }
            ],
        },
        "components": components,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic CycloneDX SBOM.")
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)

    text = json.dumps(generate_sbom(args.version), indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
