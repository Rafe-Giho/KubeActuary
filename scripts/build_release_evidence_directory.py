#!/usr/bin/env python3
"""Build release evidence artifacts from a local evidence directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_external_evidence_bundle import build_bundle  # noqa: E402
from scripts.build_live_evidence_manifest import MANIFEST_SCHEMA, build_manifest  # noqa: E402
from scripts.evaluate_external_gate_evidence import SUPPLEMENTAL_SCHEMA, load_supplemental  # noqa: E402
from scripts.validate_live_evidence import SUPPORTED_SCHEMAS, validate_file  # noqa: E402


GENERATED_SCHEMAS = {
    MANIFEST_SCHEMA,
    "kube-actuary.external-gate-evaluation.v1",
    "kube-actuary.external-evidence-bundle.v1",
}
DEFAULT_OUTPUT_DIR = ".kubeactuary"


def json_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return payload


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def scan_directory(
    evidence_dir: Path,
    output_dir: Path,
    require_live_reports: bool = True,
) -> tuple[list[Path], list[Path], list[str]]:
    live_reports: list[Path] = []
    supplemental: list[Path] = []
    errors: list[str] = []
    output_dir = output_dir.resolve()
    ignored_dirs = {output_dir, (evidence_dir / DEFAULT_OUTPUT_DIR).resolve()}
    for path in sorted(evidence_dir.rglob("*.json")):
        resolved = path.resolve()
        if any(is_relative_to(resolved, ignored) for ignored in ignored_dirs):
            continue
        try:
            payload = json_payload(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        schema = payload.get("schemaVersion")
        if schema in SUPPORTED_SCHEMAS:
            file_errors = validate_file(path)
            if file_errors:
                errors.extend(file_errors)
            else:
                live_reports.append(path)
        elif schema == SUPPLEMENTAL_SCHEMA:
            try:
                load_supplemental(path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
            else:
                supplemental.append(path)
        elif schema in GENERATED_SCHEMAS:
            continue
        else:
            errors.append(f"{path}: unsupported evidence schemaVersion: {schema!r}")
    if require_live_reports and not live_reports:
        errors.append(f"{evidence_dir}: no live evidence report JSON files found")
    return live_reports, supplemental, errors


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_directory(evidence_dir: Path, output_dir: Path) -> dict[str, Any]:
    if not evidence_dir.is_dir():
        raise ValueError(f"{evidence_dir}: evidence directory not found")
    live_reports, supplemental, errors = scan_directory(evidence_dir, output_dir)
    if errors:
        raise ValueError("; ".join(errors))

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "live-evidence-manifest.json"
    bundle_path = output_dir / "external-evidence-bundle.json"
    write_json(manifest_path, build_manifest(live_reports))
    bundle = build_bundle(manifest_path, supplemental)
    write_json(bundle_path, bundle)
    return {
        "manifest": manifest_path,
        "bundle": bundle_path,
        "liveReports": len(live_reports),
        "supplementalEvidence": len(supplemental),
        "closure": bundle.get("closure", {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build KubeActuary release evidence artifacts from a directory.")
    parser.add_argument("evidence_dir", help="directory containing captured live and supplemental evidence JSON")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"artifact output directory, default: <evidence-dir>/{DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    output_dir = Path(args.output_dir) if args.output_dir else evidence_dir / DEFAULT_OUTPUT_DIR
    try:
        result = build_directory(evidence_dir, output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("release-evidence-directory: failed")
        print(f"error: {exc}")
        return 1

    closure = result["closure"]
    print("release-evidence-directory: passed")
    print(f"live-reports: {result['liveReports']}")
    print(f"supplemental: {result['supplementalEvidence']}")
    print(f"closure: {closure.get('status', 'unknown')}")
    print(f"manifest: {result['manifest']}")
    print(f"bundle: {result['bundle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
