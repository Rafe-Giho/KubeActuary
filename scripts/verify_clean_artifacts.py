#!/usr/bin/env python3
"""Verify generated Python cache artifacts are absent from the workspace."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIPPED_DIRS = {".git", ".venv", "build", "dist"}
BYTECODE_SUFFIXES = {".pyc", ".pyo"}


def iter_artifacts(root: Path) -> tuple[list[Path], list[Path]]:
    cache_dirs: list[Path] = []
    bytecode_files: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for child in current.iterdir():
            if child.is_dir():
                if child.name in SKIPPED_DIRS:
                    continue
                if child.name == "__pycache__":
                    cache_dirs.append(child)
                    continue
                stack.append(child)
            elif child.suffix in BYTECODE_SUFFIXES:
                bytecode_files.append(child)
    return sorted(cache_dirs), sorted(bytecode_files)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    cache_dirs, bytecode_files = iter_artifacts(ROOT)
    if cache_dirs or bytecode_files:
        print("clean-artifacts: failed")
        for path in cache_dirs:
            print(f"error: python cache directory remains: {rel(path)}")
        for path in bytecode_files:
            print(f"error: python bytecode file remains: {rel(path)}")
        return 1

    print("clean-artifacts: passed")
    print("python-cache-dirs: 0")
    print("python-bytecode-files: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
