# Krew Manifest

KubeActuary can generate a Krew manifest for the `kubectl-actuary` plugin from
release archives.

## Generate Archives

```sh
python3 -B scripts/package_release_archives.py --version 0.2.0 --output-dir dist
```

## Generate Manifest

```sh
python3 -B scripts/generate_krew_manifest.py \
  --version 0.2.0 \
  --archive-dir dist \
  --output dist/actuary.yaml
```

The manifest name is `actuary`, which installs as `kubectl actuary` through
Krew. It maps both `kubectl-actuary` and its adjacent `kube-actuary` helper into
the plugin install directory.

## Verification

```sh
python3 -B scripts/verify_krew_manifest.py
```

The verifier creates release archives in a temporary directory, generates the
manifest, checks all platform entries and SHA-256 digests, and verifies the
plugin file mappings.

If Krew is installed, run the generated manifest through:

```sh
kubectl krew install --manifest dist/actuary.yaml
```

For a repeatable smoke command with isolated local filesystem writes:

```sh
python3 -B scripts/run_krew_smoke.py
python3 -B scripts/run_krew_smoke.py --manifest dist/actuary.yaml --run --output /tmp/kubeactuary-krew-smoke.json
```

Run mode sets `KREW_ROOT` to an isolated temporary directory unless
`--krew-root` is provided. It does not contact a Kubernetes cluster. The
manifest URI may still require network access depending on where the release
archives are hosted.

The optional `--output` file uses `kube-actuary.krew-smoke.v1` and records the
manifest path, `clusterAccess: none`, `filesystemWrites: isolated-krew-root`,
the command, isolated KREW_ROOT, exit code, and raw stdout/stderr.

The local verifier does not require Krew and does not install the plugin.
