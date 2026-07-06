#!/usr/bin/env python3
"""Bundle live and supplemental evidence with gate evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_live_evidence_coverage import load_manifest  # noqa: E402
from scripts.evaluate_external_gate_evidence import evaluate, load_supplemental  # noqa: E402


SCHEMA_VERSION = "kube-actuary.external-evidence-bundle.v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def build_bundle(manifest_path: Path, supplemental_paths: list[Path]) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    supplemental_records = [load_supplemental(path) for path in supplemental_paths]
    evaluation = evaluate(manifest, supplemental_paths)
    summary = evaluation.get("summary", {})
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "manifest": {
            **file_record(manifest_path),
            "schemaVersion": manifest.get("schemaVersion"),
            "reports": len(manifest.get("reports", [])) if isinstance(manifest.get("reports"), list) else 0,
        },
        "supplementalEvidence": [
            {
                **file_record(path),
                "schemaVersion": record.get("schemaVersion"),
                "kind": record.get("kind"),
                "ok": record.get("ok"),
                "summary": record.get("summary"),
            }
            for path, record in zip(supplemental_paths, supplemental_records)
        ],
        "evaluation": evaluation,
        "closure": {
            "status": "complete" if summary.get("uncovered") == 0 else "partial",
            "covered": summary.get("covered", 0),
            "uncovered": summary.get("uncovered", 0),
            "total": summary.get("total", 0),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a KubeActuary external evidence bundle.")
    parser.add_argument("manifest", help="live evidence manifest JSON")
    parser.add_argument("--evidence", action="append", default=[], help="supplemental external evidence JSON")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        bundle = build_bundle(Path(args.manifest), [Path(path) for path in args.evidence])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("external-evidence-bundle: failed")
        print(f"error: {exc}")
        return 1

    encoded = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(encoded, end="")
    else:
        Path(args.output).write_text(encoded)
        print(f"external-evidence-bundle: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
