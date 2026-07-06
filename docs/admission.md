# Optional Admission Prototype

KubeActuary admission is optional. The default local and CLI workflows do not
install a webhook and do not require cluster admission control.

The prototype manifest lives at:

```sh
deploy/admission/validatingwebhookconfiguration.yaml
```

Safety defaults:

- `failurePolicy: Ignore` so webhook outage does not block cluster writes;
- `timeoutSeconds: 2` to keep admission latency bounded;
- namespace opt-in through `kubeactuary.dev/admission: enabled`;
- no webhook server deployment in this seed;
- no direct Kubernetes write execution by KubeActuary.

AI identity selector:

- requests from members of `kubeactuary.dev/ai-writers` are selected;
- requests from service accounts with username prefix
  `system:serviceaccount:ai-agents:` are selected;
- other identities are ignored by the KubeActuary admission policy.

Required annotations for selected write requests:

- `kubeactuary.dev/capsule`
- `kubeactuary.dev/capsule-digest`

The v0.8.1 policy check only verifies selector and annotation presence. Digest
and gate tamper checks are handled by the later v0.8.2 fixture set.

Verification:

```sh
python3 -B scripts/verify_admission_webhook.py
python3 -B scripts/verify_admission_policy.py
```

Live kind smoke remains a release-gate item when `kind` is available locally.
