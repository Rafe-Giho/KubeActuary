#!/usr/bin/env python3
"""Verify generated Krew manifest contract without requiring Krew."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGER = ROOT / "scripts" / "package_release_archives.py"
GENERATOR = ROOT / "scripts" / "generate_krew_manifest.py"
SMOKE = ROOT / "scripts" / "run_krew_smoke.py"
DOC = ROOT / "docs" / "krew.md"
VERSION = (ROOT / "VERSION").read_text().strip()
TARGETS = ("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64")


def run_python(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_fake_smoke(tmpdir: Path) -> tuple[subprocess.CompletedProcess[str], dict, list[list[str]], str | None]:
    manifest = tmpdir / "actuary.yaml"
    manifest.write_text("apiVersion: krew.googlecontainertools.github.com/v1alpha2\nkind: Plugin\n")
    output = tmpdir / "krew-smoke.json"
    log_path = tmpdir / "kubectl-calls.json"
    env_path = tmpdir / "krew-root.txt"
    krew_root = tmpdir / "krew-root"
    kubectl = tmpdir / "kubectl"
    kubectl.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import os",
                "import sys",
                "from pathlib import Path",
                f"log_path = Path({str(log_path)!r})",
                f"env_path = Path({str(env_path)!r})",
                "calls = json.loads(log_path.read_text()) if log_path.exists() else []",
                "calls.append(sys.argv[1:])",
                "log_path.write_text(json.dumps(calls))",
                "env_path.write_text(os.environ.get('KREW_ROOT', ''))",
                "args = sys.argv[1:]",
                "if args[:3] == ['krew', 'install', '--manifest']:",
                "    print('Installed plugin: actuary')",
                "    raise SystemExit(0)",
                "print('unexpected kubectl call', file=sys.stderr)",
                "raise SystemExit(9)",
            ]
        )
    )
    kubectl.chmod(0o755)
    result = run_python(
        SMOKE,
        "--kubectl",
        str(kubectl),
        "--manifest",
        str(manifest),
        "--krew-root",
        str(krew_root),
        "--run",
        "--output",
        str(output),
    )
    report = json.loads(output.read_text()) if output.exists() else {}
    calls = json.loads(log_path.read_text()) if log_path.exists() else []
    krew_root_seen = env_path.read_text() if env_path.exists() else None
    return result, report, calls, krew_root_seen


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
    with tempfile.TemporaryDirectory() as tmp:
        result, report, calls, krew_root_seen = run_fake_smoke(Path(tmp))
    if result.returncode != 0:
        errors.append(f"Krew smoke fake run failed: {result.stderr.strip()}")
    if "krew-smoke: passed" not in result.stdout:
        errors.append("Krew smoke fake run must pass")
    if report.get("schemaVersion") != "kube-actuary.krew-smoke.v1":
        errors.append("Krew smoke evidence schema mismatch")
    if report.get("clusterAccess") != "none":
        errors.append("Krew smoke must not require cluster access")
    if report.get("filesystemWrites") != "isolated-krew-root":
        errors.append("Krew smoke must isolate filesystem writes")
    if report.get("summary", {}).get("total") != 1 or report.get("summary", {}).get("failed") != 0:
        errors.append("Krew smoke evidence must include one successful command")
    for record in report.get("commands", []):
        if record.get("ok") is not True or "stdout" not in record or "stderr" not in record:
            errors.append("Krew smoke record must include ok/stdout/stderr")
    if calls != [["krew", "install", "--manifest", report.get("manifest")]]:
        errors.append(f"Krew smoke must run only kubectl krew install --manifest: {calls!r}")
    if not krew_root_seen or "krew-root" not in krew_root_seen:
        errors.append("Krew smoke must pass isolated KREW_ROOT to kubectl")

    for required in (
        "Krew",
        "generate_krew_manifest.py",
        "run_krew_smoke.py",
        "kubectl-actuary",
        "kubectl krew",
        "kube-actuary.krew-smoke.v1",
        "isolated KREW_ROOT",
    ):
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
