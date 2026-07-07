# Contributing

KubeActuary is a pre-GA, local-first evidence workflow for Kubernetes
operations. Contributions should keep the safety boundary explicit.

## Safety Boundary

- Do not add direct Kubernetes write execution by default.
- Keep proposed writes outside the agent tool surface.
- Keep collectors auditable and low-overhead.
- Avoid cluster-wide scans, in-cluster LLMs, and privileged defaults.
- Prefer Python standard library code unless a dependency is clearly justified.

## Development Checks

Run the local verification suite before proposing changes:

```sh
python3 -B -m unittest discover -s tests
git diff --check
```

For focused changes, also run the relevant targeted tests or examples for the
files you touched.

## Documentation

Public behavior changes should update:

- README and README.ko when the public interface changes;
- docs under `docs/` for workflow, safety, or release gates;
- tests or examples that prove the new contract.

Do not mark live Kubernetes, Helm, Krew, or managed-provider validation as done
without captured run evidence.

## Security

Report vulnerabilities through `SECURITY.md`. Do not open a public issue with
exploit details, credentials, kubeconfigs, tokens, or customer data.

## Licensing

Unless the project changes license in a future release, contributions are made
under the MIT License in `LICENSE`. Do not copy code or assets with incompatible
license terms into this repository.
