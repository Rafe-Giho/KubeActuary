#!/usr/bin/env python3
"""Create deterministic KubeActuary release archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")
PAYLOAD_FILES = (
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


def file_mode(path: Path) -> int:
    return 0o755 if os.access(path, os.X_OK) else 0o644


def add_file(tar: tarfile.TarFile, source: Path, arcname: str) -> None:
    data = source.read_bytes()
    info = tarfile.TarInfo(arcname)
    info.size = len(data)
    info.mode = file_mode(source)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def write_archive(version: str, target: str, output_dir: Path) -> Path:
    root_name = f"kube-actuary-{version}-{target}"
    archive = output_dir / f"{root_name}.tar.gz"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for relative in PAYLOAD_FILES:
            add_file(tar, ROOT / relative, f"{root_name}/{relative}")
    with gzip.GzipFile(filename="", mode="wb", fileobj=archive.open("wb"), mtime=0) as gz:
        gz.write(buffer.getvalue())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n")
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create KubeActuary release archives.")
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--target", action="append", choices=DEFAULT_TARGETS, help="target to build; repeatable")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = tuple(args.target) if args.target else DEFAULT_TARGETS
    for target in targets:
        archive = write_archive(args.version, target, output_dir)
        print(f"archive: {archive}")
        print(f"sha256: {archive}.sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
