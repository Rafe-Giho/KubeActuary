# KubeActuary Agent Notes

Be concise and practical.

Project purpose:

- KubeActuary is an evidence-carrying operations CLI for AI-assisted Kubernetes.
- Do not add direct cluster-write execution casually.
- Keep the default path model-free, auditable, and low resource overhead.
- Prefer small CLI, CRD, and controller increments over a broad agent platform.

Engineering constraints:

- No external runtime dependency unless it is clearly justified.
- Keep alpha commands usable with `python3`.
- Tests should run with `python3 -B -m unittest discover -s tests`.
- CRD/controller work should keep cluster load low: watch only KubeActuary CRDs,
  avoid cluster-wide scans, avoid in-cluster LLMs.

