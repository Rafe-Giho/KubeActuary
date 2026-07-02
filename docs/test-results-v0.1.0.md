# v0.1.0 Test Results

Run date: 2026-07-02.

## Summary

Result: passed for the v0.1.0 alpha target.

## Commands Run

### Unit Tests

```sh
python3 -B -m unittest discover -s tests
```

Result:

```text
Ran 9 tests
OK
```

### CLI Version and Help

```sh
python3 -B bin/kube-actuary --version
python3 -B bin/kube-actuary --help
python3 -B bin/kube-actuary collect auth --help
```

Result:

- version prints `kube-actuary 0.1.0`;
- help lists `collect` and `render-crd`;
- `collect auth` help is available.

### Render CRD

```sh
python3 -B bin/kube-actuary render-crd examples/read-pods.verified.capsule.json --name read-pods --namespace default
```

Result:

- rendered `apiVersion: "ops.kubeactuary.dev/v1alpha1"`;
- rendered `kind: "OperationCapsule"`;
- included proposed action, required evidence, attached evidence, and rollback
  block.

### Gate Behavior

```sh
python3 -B bin/kube-actuary gate examples/read-pods.verified.capsule.json
python3 -B bin/kube-actuary gate examples/scale-prod-deployment.capsule.json
```

Result:

- read-only verified example opened the gate;
- high-risk production scale draft kept the gate closed because evidence is
  missing.

### JSON and YAML Parsing

```sh
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/scale-prod-deployment.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; YAML.load_file("deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"); YAML.load_file("examples/operationcapsule-scale.yaml"); YAML.load_file("/private/tmp/kubeactuary-render-v010.yaml"); puts "yaml ok"'
```

Result:

- example capsule JSON files parse;
- schema JSON parses;
- CRD YAML, CR example YAML, and generated CRD object YAML parse.

### Cache Check

```sh
find . -name __pycache__ -type d -print
```

Result:

- no `__pycache__` directories found.

## Release Judgment

v0.1.0 is suitable as a local-first alpha release.

It is not production-ready as a controller or admission system because those
components are intentionally not implemented yet.

