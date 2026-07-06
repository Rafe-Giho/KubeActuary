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

The local verifier does not require Krew and does not install the plugin.
