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

Verification:

```sh
python3 -B scripts/verify_admission_webhook.py
```

Live kind smoke remains a release-gate item when `kind` is available locally.
