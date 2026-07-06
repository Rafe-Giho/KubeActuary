# Release Archives

KubeActuary is currently Python stdlib only, so release archives are source
payloads named by target platform for install tooling compatibility.

## Targets

- `linux-amd64`
- `linux-arm64`
- `darwin-amd64`
- `darwin-arm64`

## Build

```sh
python3 -B scripts/package_release_archives.py --version 0.2.0 --output-dir dist
```

Each archive includes:

- `bin/kube-actuary`
- `bin/kubectl-actuary`
- `bin/kube-actuary-controller`
- controller helper modules
- CRD seed
- JSON Schema
- README files
- `LICENSE`
- `VERSION`

Each archive also gets a `.sha256` sidecar.

## Verification

```sh
python3 -B scripts/verify_release_archives.py
```

The verifier creates archives in a temporary directory, checks SHA-256 sidecars,
validates archive contents and executable bits, extracts one archive, and runs
CLI/plugin/controller smoke checks.
