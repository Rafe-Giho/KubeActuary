#!/usr/bin/env python3
"""Local stdlib AdmissionReview HTTP server for KubeActuary policy checks."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_admission_review import admission_response


def server_config(host: str, port: int) -> dict:
    return {
        "host": host,
        "port": port,
        "paths": ["/healthz", "/validate"],
        "clusterAccess": "none",
        "writeExecution": "disabled",
    }


def serve(host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def send_body(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self.send_body(200, "application/json", b'{"status":"ok"}\n')
            else:
                self.send_body(404, "text/plain", b"not found\n")

        def do_POST(self) -> None:
            if self.path != "/validate":
                self.send_body(404, "text/plain", b"not found\n")
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                response = admission_response(payload)
                body = json.dumps(response, sort_keys=True).encode("utf-8") + b"\n"
                self.send_body(200, "application/json", body)
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, sort_keys=True).encode("utf-8") + b"\n"
                self.send_body(400, "application/json", body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"kube-actuary-admission-server http://{host}:{port}", flush=True)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve local KubeActuary AdmissionReview policy checks.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9443)
    parser.add_argument("--print-config", action="store_true")
    args = parser.parse_args(argv)

    if args.print_config:
        print(json.dumps(server_config(args.host, args.port), indent=2, sort_keys=True))
        return 0

    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
