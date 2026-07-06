# Supply Chain Artifacts

KubeActuary generates local, deterministic supply-chain metadata without adding
runtime dependencies.

## SBOM

```sh
python3 -B scripts/generate_sbom.py --version 0.2.0 --output dist/kube-actuary-0.2.0.sbom.json
```

The SBOM uses CycloneDX JSON and records SHA-256 hashes for repository files
that make up the CLI, CRD, examples, packaging, tests, and documentation.

## Provenance

First generate release archives:

```sh
python3 -B scripts/package_release_archives.py --version 0.2.0 --output-dir dist
```

Then generate provenance:

```sh
python3 -B scripts/generate_provenance.py \
  --version 0.2.0 \
  --artifact-dir dist \
  --output dist/kube-actuary-0.2.0.provenance.json
```

The provenance is an in-toto statement using the SLSA provenance v1 predicate.
It records the release archive subjects and SHA-256 digests.

## Verification

```sh
python3 -B scripts/verify_supply_chain.py
```

The verifier creates archives in a temporary directory, validates the SBOM
schema fields, checks provenance subjects against archive digests, and confirms
the supply-chain docs reference the expected tools.
