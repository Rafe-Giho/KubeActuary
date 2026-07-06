#!/usr/bin/env python3
"""Verify generated local artifacts are absent or ignored."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIPPED_DIRS = {".git", ".venv", "build", "dist"}
BYTECODE_SUFFIXES = {".pyc", ".pyo"}
REQUIRED_GITIGNORE_LINES = {"evidence/live/"}


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
    gitignore = ROOT / ".gitignore"
    ignored_lines = {
        line.strip()
        for line in gitignore.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing_ignores = sorted(REQUIRED_GITIGNORE_LINES - ignored_lines)
    if cache_dirs or bytecode_files or missing_ignores:
        print("clean-artifacts: failed")
        for path in cache_dirs:
            print(f"error: python cache directory remains: {rel(path)}")
        for path in bytecode_files:
            print(f"error: python bytecode file remains: {rel(path)}")
        for pattern in missing_ignores:
            print(f"error: local evidence directory must be ignored: {pattern}")
        return 1

    print("clean-artifacts: passed")
    print("python-cache-dirs: 0")
    print("python-bytecode-files: 0")
    print("local-evidence-ignored: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
