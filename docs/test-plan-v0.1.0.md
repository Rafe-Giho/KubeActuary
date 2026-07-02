# v0.1.0 Test Plan

Run these checks before tagging v0.1.0.

## Automated

```sh
python3 -B -m unittest discover -s tests
```

Expected:

- all tests pass;
- no `__pycache__` directories are left behind when using `-B`.

## CLI Smoke Tests

```sh
python3 -B bin/kube-actuary --version
python3 -B bin/kube-actuary --help
python3 -B bin/kube-actuary collect auth --help
python3 -B bin/kube-actuary render-crd examples/read-pods.verified.capsule.json --name read-pods --namespace default
python3 -B bin/kube-actuary gate examples/read-pods.verified.capsule.json
python3 -B bin/kube-actuary gate examples/scale-prod-deployment.capsule.json
```

Expected:

- version prints `kube-actuary 0.1.0`;
- help includes `collect` and `render-crd`;
- render output is an `ops.kubeactuary.dev/v1alpha1` `OperationCapsule`;
- verified read-only example opens the gate;
- high-risk draft example keeps the gate closed.

## Format Checks

```sh
python3 -B -m json.tool examples/read-pods.verified.capsule.json
python3 -B -m json.tool examples/scale-prod-deployment.capsule.json
python3 -B -m json.tool schemas/operation-capsule.v0alpha1.schema.json
ruby -e 'require "yaml"; YAML.load_file("deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"); YAML.load_file("examples/operationcapsule-scale.yaml"); puts "yaml ok"'
```

Expected:

- JSON examples parse;
- schema JSON parses;
- CRD YAML and example CR YAML parse.

## Safety Checks

Confirm from code and tests:

- `collect auth` runs only `kubectl auth can-i`;
- proposed mutation commands are not executed by `gate`, `verify`, or
  `collect auth`;
- failed evidence closes the gate.

