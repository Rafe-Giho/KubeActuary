# Live Validation Readiness

This ledger tracks validation that cannot be honestly marked `DONE` from local
offline checks alone. The verifier is inventory-only: it checks local tool
availability and required documentation, but does not contact a cluster, does not contact cloud APIs, and does not create, update, or delete Kubernetes resources.

Run:

```sh
python3 -B scripts/verify_live_validation_readiness.py
python3 -B scripts/verify_live_validation_readiness.py --json
python3 -B scripts/verify_live_validation_readiness.py --probe-environment
python3 -B scripts/generate_release_progress.py --format markdown --probe-environment
python3 -B scripts/generate_release_progress.py --format text --version 0.4.3
python3 -B scripts/generate_release_progress.py --format markdown --version 0.4.3
python3 -B scripts/generate_release_progress.py --format markdown --evidence-dir evidence/live
python3 -B scripts/generate_live_validation_queue.py --format markdown
python3 -B scripts/generate_live_validation_queue.py --format markdown --probe-environment
python3 -B scripts/generate_live_validation_queue.py --format markdown --evidence-dir evidence/live
python3 -B scripts/generate_version_worklist.py --format markdown --open-only --evidence-dir evidence/live
python3 -B scripts/record_version_blockers.py --format markdown --evidence-dir evidence/live
python3 -B scripts/record_version_blockers.py --evidence-dir evidence/live --record
python3 -B scripts/generate_version_unblock_plan.py --format markdown --evidence-dir evidence/live
python3 -B scripts/generate_version_unblock_plan.py --evidence-dir evidence/live --record
python3 -B scripts/select_next_unblock_action.py --format markdown --evidence-dir evidence/live
python3 -B scripts/select_next_unblock_action.py --evidence-dir evidence/live --record
python3 -B scripts/run_next_unblock_action.py evidence/live
python3 -B scripts/run_next_unblock_action.py evidence/live --run --record
python3 -B scripts/select_next_version_task.py --evidence-dir evidence/live
python3 -B scripts/select_next_version_task.py --evidence-dir evidence/live --skip-complete-evidence
python3 -B scripts/verify_live_validation_queue.py
python3 -B scripts/verify_live_validation_queue_safety.py
python3 -B scripts/prepare_live_evidence_directory.py evidence/live
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --version 0.4.3
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --skip-complete-evidence
python3 -B scripts/verify_live_evidence_directory_scaffold.py
python3 -B scripts/verify_live_evidence_schema.py
python3 -B scripts/verify_live_evidence_manifest.py
python3 -B scripts/verify_live_evidence_coverage.py
python3 -B scripts/verify_external_gate_plan.py
python3 -B scripts/verify_external_gate_command_safety.py
python3 -B scripts/verify_external_gate_evidence.py
python3 -B scripts/verify_external_evidence_builder.py
python3 -B scripts/verify_external_evidence_bundle.py
python3 -B scripts/verify_release_evidence_directory.py
python3 -B scripts/verify_release_evidence_status.py
```

Expected:

```text
live-validation-readiness: passed
mode: inventory-only
tool-ready-gates: <ready>/<total>
cluster-writes: disabled
```

Optional environment probe output:

```text
environment-probe: available|unavailable|kubectl-unavailable
blocked-by-environment: <count>
```

The JSON form includes `gateToolReadiness`, which lists each live gate, the
required local tools, missing tools, and whether the gate is `tool-ready` from an
inventory perspective.

With `--probe-environment`, the readiness verifier and queue generator run
read-only `kubectl` checks to classify current cluster availability. They do not
create, update, patch, or delete Kubernetes resources. Environment-blocked gates
are reported as `blocked-by-environment` so local worklists can distinguish
"tool installed" from "disposable cluster not reachable". The environment probe
also records a stable `reason` such as `connection-refused`,
`network-not-permitted`, or `kubeconfig-missing` so repeated local validation
can compare why a cluster is unavailable without parsing raw `kubectl` stderr.

The release progress report can also run `--probe-environment` directly to
classify tool-ready actions as environment-blocked when a disposable cluster is
not reachable. The probe is read-only and uses the same stable reason labels as
the readiness verifier. Use `--version <version>` to narrow the release progress
view to one version's rows, external gates, and next actions during repeated
local validation. `prepare_live_evidence_directory.py --version <version>`
uses the same scope for the persisted selected next-task artifacts in
`.kubeactuary/`. It can also inspect `--evidence-dir`. If that
directory has not been prepared yet, it reports `not-prepared` instead of
failing and prints the `prepare_live_evidence_directory.py` command needed to
start the local evidence loop. For prepared directories, the Markdown progress
view lists every open item under its version and surfaces the selected next
task, next-task runner status, next-task runner failure reason,
environment probe/blocker status, and latest iteration advance status,
including run id and history run count. It also
prints the selected next-task evidence files and resolved commands, so the
local capture target is visible without opening the evidence status JSON. It also
prints every action blocker, filtered worklist commands for each blocker, and
queue-source details from the selected next-task, runner, and advance records
when an evidence directory has been prepared.
When a prepared evidence directory already contains a failed environment probe,
the progress view keeps the probe command in `environmentProbeRetry` with a
retry condition instead of presenting the same failed probe as immediate work.
It also prints every tool-ready
action and evidence next command instead of truncating runnable local work. The
same progress view summarizes repeated missing-tool and environment blockers,
so the remaining local task loop can distinguish installation work from
disposable-cluster setup.
If the prepared directory contains `.kubeactuary/live-validation-queue.json`,
progress uses that persisted queue as the next-action source so action counts
match the last local probe instead of the inventory-only tool snapshot.
Progress JSON only fills `nextActions.actions[].firstCommand` for `tool-ready`
actions; blocked actions keep their blocker and next-step metadata without
presenting a runnable command.
Evidence-aware version worklists and next-task selection use that same
prepared queue when `--evidence-dir` is passed, so local iteration commands
show the last probed environment blockers until the directory is refreshed.
Their Markdown/text output also prints the queue source, making prepared queue
reuse visible during repeated local verification. Worklist Markdown also prints
missing tools and next steps per item, and worklist text output keeps the same
local task summary available without Markdown rendering, so blocked local loops
remain actionable.
`record_version_blockers.py` turns that same prepared queue snapshot into a
dedicated local blocker ledger. With `--record`, it writes
`.kubeactuary/version-blockers.json` and `.kubeactuary/version-blockers.md`
under the evidence directory, preserving version groups, affected versions,
filtered worklist drilldowns, environment reasons, next steps, and evidence file
readiness without running cluster or cloud commands.
`generate_version_unblock_plan.py` converts that blocker ledger into a local
unblock plan with one action per missing tool or environment blocker. The plan
lists read-only verification commands such as tool version checks and
`kubectl cluster-info --request-timeout=5s`, plus queue refresh and metadata
recording commands. With `--record`, it writes
`.kubeactuary/version-unblock-plan.json` and
`.kubeactuary/version-unblock-plan.md` without installing tools or starting
clusters.
`select_next_unblock_action.py` narrows that plan to one deterministic next
blocker using the highest item count, then kind and target name for stable
ties. With `--record`, it writes `.kubeactuary/next-unblock-action.json` and
`.kubeactuary/next-unblock-action.md`, preserving the read-only verify,
refresh, inspect, and record commands for the selected blocker.
`run_next_unblock_action.py` loads `.kubeactuary/next-unblock-action.json` and
validates only the selected `verify` commands. Without `--run`, it reports the
plan. With `--run --record`, it executes only allowlisted tool-version or
`kubectl cluster-info --request-timeout=5s` checks and records
`.kubeactuary/next-unblock-action-run.json` with schema
`kube-actuary.next-unblock-action-run.v1`, plus Markdown status without running
refresh, inspect, record, install, or write commands.
It also summarizes every repeated missing-tool and environment blocker across
the whole worklist and per version, including environment reasons such as
`connection-refused`, so repeated validation can focus on the shared blocker
before re-running evidence commands. Blocker summaries include filtered
worklist commands that preserve the evidence directory and version context when
they are active. Use `--capture-status`, `--missing-tool`,
`--environment-status`, and `--environment-reason` on worklist, next-task,
iteration-pack, iteration-history, live-evidence scaffold, and
version-iteration advance commands to keep a local loop focused on one blocker
class.
Version iteration packs preserve the same queue source, blocker summaries,
and blocker drilldown commands in their index and per-version files. Version
iteration history records and status output keep that source plus the latest
blocker summaries and drilldown commands, so run-to-run comparisons remain
traceable and actionable. History status can be emitted as text, JSON, or
Markdown, and `--record` writes `status.json` and `status.md` into the history
directory. It also includes latest run filters, latest run/worklist/diff
artifact paths, the selected latest next task, immediate next local loop
commands for refreshing the recorded status, and deferred retry commands on
blocker actions for rerunning the latest iteration filters after the blocker is
resolved. When
a latest task has resolved evidence files, history status lists each file role,
path, and readiness so the next capture target is visible from the status
report. When
a latest run has a diff from the prior run, history status surfaces both
aggregate and per-version diff summaries so repeated validation can distinguish
no-op reruns from changed evidence readiness or blocker state for each release
line. When the latest run used `--probe-environment`, history status also shows
the failed probe checks and messages. Persisted next-task runner and
version-iteration advance reports keep it too, so recorded local execution
state stays tied to the queue snapshot that selected the task. If the latest
tool-ready advance failed before a probe classified the environment, history
next commands add `--probe-environment` to the next advance retry so the local
loop does not blindly repeat the same live capture failure.

The queue generator uses schema `kube-actuary.live-validation-queue.v1` and
turns the current taskboard gates into an ordered evidence collection queue. It
does not run the listed commands; it only records each gate's commands, missing
tools, and closure commands. With `--evidence-dir`, it also emits deterministic
resolved command paths under `reports/`, `raw/`, `supplemental/`, and
`.kubeactuary/`. The queue safety verifier inspects both placeholder and
resolved queue commands and rejects commands outside the dry-run, read-only, or
local evidence-helper set.

Use `prepare_live_evidence_directory.py` to create the local `reports/`, `raw/`,
`supplemental/`, and `.kubeactuary/` scaffold plus queue snapshots and
`kube-actuary.next-version-task.v1` next-task artifacts before capturing
external evidence. The next-task artifacts are generated by
`select_next_version_task.py` and include resolved paths for the selected
task's raw and supplemental evidence files. When the evidence directory already
contains a prepared live validation queue, `select_next_version_task.py
--evidence-dir <dir>` uses that queue instead of rebuilding an inventory-only
view. Add `--runnable-only` when you only want `tool-ready` work; if every
remaining item is blocked by tools or environment, the selector reports no
selected task and summarizes the skipped non-runnable candidates. Use
`--blocked-only` for the inverse loop when you want the next blocker to resolve
instead of the next runnable capture task.
The default `evidence/live/` path is ignored by git because it can contain
machine-local paths, timestamps, raw command output, and failed-run diagnostics.
After a selected task's raw file is captured, `build_next_task_evidence.py`
can build that task's local supplemental evidence from the resolved
`build_external_evidence.py` command. It reads prepared local files only and
does not run cluster, cloud, or workload write commands.
With `--record`, it also writes
`.kubeactuary/next-task-evidence-build.json` and Markdown status next to the
other local iteration records.

```sh
python3 -B scripts/build_next_task_evidence.py evidence/live
python3 -B scripts/build_next_task_evidence.py evidence/live --format markdown --record
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --skip-complete-evidence
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --missing-tool kind
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --runnable-only
python3 -B scripts/prepare_live_evidence_directory.py evidence/live --blocked-only
```

## Open Live Gates

Generate the current external gate plan from the release taskboard:

```sh
python3 -B scripts/generate_external_gate_plan.py --format markdown
python3 -B scripts/generate_external_gate_plan.py --format json --output /tmp/kubeactuary-external-gates.json
```

| Gate | Current local evidence | Required live evidence |
| --- | --- | --- |
| CRD apply and explain smoke | offline CRD compatibility, upgrade, and explain checks | kind or minikube server-side dry-run plus `kubectl explain` output |
| Controller resource budget | parser and budget contract | `kubectl top pod --containers` sample under the target controller deployment |
| Lightweight cluster smoke | plan verifier for kind, minikube, MicroK8s, and k3s | successful run output for each provider |
| Helm install path | chart contract verifier | `helm template` and install smoke against a disposable cluster |
| Krew install path | manifest verifier | `kubectl krew install --manifest` smoke |
| Managed Kubernetes smoke | compatibility notes and smoke harness for providers | provider run evidence for EKS, GKE, and AKS |
| Admission webhook smoke | offline optional webhook verifier | kind admission request smoke with opt-in namespace |

## Evidence Rules

- Use disposable clusters or explicitly approved test clusters only.
- Prefer server-side dry-run for CRD, RBAC, and chart checks.
- Do not run proposed workload writes as part of KubeActuary validation.
- Attach raw command output, cluster version, tool version, and timestamp.
- Keep provider run evidence separate from offline verifier output.
- For lightweight cluster smoke runs, use
  `scripts/run_lightweight_cluster_smoke.py --run --output <path>` and keep the
  `kube-actuary.lightweight-smoke.v1` report.
- For Helm chart smoke runs, use
  `scripts/run_helm_smoke.py --run --output <path>` and keep the
  `kube-actuary.helm-smoke.v1` report.
- For Krew install smoke runs, use
  `scripts/run_krew_smoke.py --run --output <path>` and keep the
  `kube-actuary.krew-smoke.v1` report.
- For admission kind smoke runs, use
  `scripts/run_admission_kind_smoke.py --run --output <path>` and keep the
  `kube-actuary.admission-kind-smoke.v1` report.
- For managed Kubernetes smoke runs, use `scripts/run_managed_kubernetes_smoke.py`
  with `--provider <eks|gke|aks> --run --output <path>` and keep the
  `kube-actuary.managed-kubernetes-smoke.v1` report.
- Validate captured reports before using them as release evidence:

```sh
python3 -B scripts/validate_live_evidence.py <evidence.json> [...]
```

- Build a release evidence manifest after validation:

```sh
python3 -B scripts/build_live_evidence_manifest.py <evidence.json> [...] --output /tmp/kubeactuary-live-evidence-manifest.json
```

The manifest uses schema `kube-actuary.live-evidence-manifest.v1`, records each
report SHA-256, and maps captured reports to release gates such as
`lightweight-cluster-smoke`, `helm-smoke`, `krew-smoke`,
`admission-kind-smoke`, and `managed-kubernetes-smoke`.

Check release-gate coverage from a manifest:

```sh
python3 -B scripts/check_live_evidence_coverage.py /tmp/kubeactuary-live-evidence-manifest.json
python3 -B scripts/evaluate_external_gate_evidence.py /tmp/kubeactuary-live-evidence-manifest.json
```

The coverage check requires passing `mode: run` reports for kind, minikube,
MicroK8s, and k3s; EKS, GKE, and AKS; plus Helm, Krew, and admission smoke
reports. The verifier prints `required-providers: 7` when this local coverage
contract is satisfied.

The external gate evaluator maps that same manifest back to the taskboard
`VERIFY` rows. It intentionally leaves resource-budget and live
`kubectl explain` rows uncovered until those separate raw outputs are captured.
Supplemental evidence files use schema `kube-actuary.external-evidence.v1` with
`kind` set to `kubectl-explain`, `controller-resource-budget`, or
`controller-live-loop`. Controller resource budget capture prints
`controller-resource-capture` in text mode. Its supplemental evidence is
derived from the structured `kube-actuary.controller-resource-measurement.v1`
helper output and records observed CPU, memory, sample count, budget values,
and source SHA-256:

```sh
python3 -B scripts/build_external_evidence.py --kind kubectl-explain --source <kubectl-explain-output.txt> --output <external-evidence.json>
python3 -B scripts/capture_controller_resource_budget.py --output <kubectl-top-output.txt>
python3 -B scripts/capture_controller_resource_budget.py --output <kubectl-top-output.txt> --run
python3 -B scripts/build_external_evidence.py --kind controller-resource-budget --source <kubectl-top-output.txt> --output <external-evidence.json>
python3 -B scripts/build_external_evidence.py --kind controller-live-loop --source <controller-loop-output.json> --output <external-evidence.json>
python3 -B scripts/evaluate_external_gate_evidence.py /tmp/kubeactuary-live-evidence-manifest.json --evidence <external-evidence.json>
python3 -B scripts/build_external_evidence_bundle.py /tmp/kubeactuary-live-evidence-manifest.json --evidence <external-evidence.json> --output <bundle.json>
```

Evidence bundles use schema `kube-actuary.external-evidence-bundle.v1` and
record input file SHA-256 digests plus the external gate evaluation result.

For repeated local release checks, keep captured live report JSON files and
supplemental evidence JSON files in a single evidence directory:

```sh
python3 -B scripts/build_release_evidence_directory.py <evidence-dir>
```

The directory builder writes `<evidence-dir>/.kubeactuary/live-evidence-manifest.json`
and `<evidence-dir>/.kubeactuary/external-evidence-bundle.json`, ignores those
generated files and other `.kubeactuary` metadata on rerun or custom
`--output-dir` runs, and prints `release-evidence-directory: passed` when the
directory is valid. It does not contact clusters or cloud APIs.

Inspect a partial evidence directory while gathering external runs:

```sh
python3 -B scripts/inspect_release_evidence_directory.py <evidence-dir>
python3 -B scripts/inspect_release_evidence_directory.py <evidence-dir> --format json
python3 -B scripts/inspect_release_evidence_directory.py <evidence-dir> --format markdown
python3 -B scripts/inspect_release_evidence_directory.py <evidence-dir> --version 0.4.3
python3 -B scripts/inspect_release_evidence_directory.py <evidence-dir> --record
```

The status inspector uses schema `kube-actuary.release-evidence-status.v1`,
reports covered and uncovered external gates, prints next evidence commands,
and includes the persisted `kube-actuary.next-version-task.v1` artifact when
the evidence directory was prepared by the scaffold. It does not require
complete release closure. Text and Markdown output both report whether resolved
next-task raw input and supplemental output files are present or still missing,
and print every selected next-task command. They also print every computed next
command instead of truncating local follow-up work. When the prepared live
validation queue is available, `nextCommands` uses the queue's resolved
evidence paths for all uncovered gates instead of repeating placeholder
commands. When
present, it also reports the latest `kube-actuary.next-version-task-run.v1`
runner status from `.kubeactuary/next-version-task-run.json` and the local
environment probe/blocker metadata from `.kubeactuary/environment-*.json`,
plus the latest advance workflow status from
`.kubeactuary/version-iteration-advance.json`. With `--record`, it persists
the computed status as `.kubeactuary/release-evidence-status.json` and
`.kubeactuary/release-evidence-status.md`. The status report preserves and
prints queue-source metadata from the next-task, runner, and advance records
when present. For older prepared evidence directories whose records do not yet
carry explicit queue-source fields, the inspector infers
`prepared-live-validation-queue` from `.kubeactuary/live-validation-queue.json`
and reports the queue-source origin so explicit and inferred status metadata
remain distinguishable. It also compares the persisted selected next-task
artifact with the live validation queue and reports whether the id, status,
kind, and resolved commands still match, making stale next-task artifacts
visible before another capture attempt. The same status and progress reports
compare persisted runner and advance records against the current next-task
artifact, so stale local execution records are visible before repeated
iteration. Use `--version <version>` to keep coverage totals, missing gates,
blocker drilldowns, and environment-probe follow-up commands scoped to one
release version. The status `nextCommands` list recommends only commands whose
prepared queue item is `tool-ready`; `missing-tools` and
`blocked-by-environment` actions stay in blocker summaries and next-step text
instead of being suggested as runnable capture commands. When a selected
next-unblock verifier exists and has not passed, the same list also includes
`run_next_unblock_action.py <evidence-dir> --run --record` so the local loop can
recheck the blocker after the missing tool or environment condition changes.
If an environment probe has not run yet, `nextCommands` can recommend the
read-only probe first. If the probe already failed, the status report preserves
the exact probe command in `environmentProbeRetry` and marks it deferred until
cluster access is available. Status and progress output also include
`deferredCommands`, a separate local task list for retry commands that should be
held until their `retryAfter` condition is true.
When `generate_release_progress.py` receives both `--evidence-dir` and an empty
`--history-dir`, the version-history section also prints the initial
`record_version_iteration.py <history-dir> --evidence-dir <evidence-dir>`
command needed to bootstrap repeated local snapshots.
Release progress uses the same rule for `nextActions.actions[].firstCommand`.
The next-task evidence builder reports schema
`kube-actuary.next-task-evidence-build.v1` when converting prepared raw files
into local supplemental evidence records. Add `--record` to persist
`.kubeactuary/next-task-evidence-build.json` and
`.kubeactuary/next-task-evidence-build.md`; release evidence status then
reports the latest build status and selected next-task consistency.

The selected next-task runner validates the persisted
`kube-actuary.next-version-task.v1` commands before execution. Without `--run`
it prints a plan only; with `--run` it executes the selected commands and
reports schema `kube-actuary.next-version-task-run.v1`. If the selected task is
not `tool-ready`, `--run` records a zero-run status such as
`blocked-by-environment` or `missing-tools` instead of executing capture
commands. Runner text, JSON, and recorded Markdown include the selected queue
source. Add `--record` to
persist the runner report as `.kubeactuary/next-version-task-run.json` and
`.kubeactuary/next-version-task-run.md`:

```sh
python3 -B scripts/run_next_version_task.py <evidence-dir>
python3 -B scripts/run_next_version_task.py <evidence-dir> --format markdown
python3 -B scripts/run_next_version_task.py <evidence-dir> --run
python3 -B scripts/run_next_version_task.py <evidence-dir> --run --record
```

If the selected next-task artifact is missing, both
`run_next_version_task.py` and `build_next_task_evidence.py` fail with the
`prepare_live_evidence_directory.py` command needed to initialize the directory.
Failed runner reports include a `failure` summary and preserve the first
actionable command error in text, JSON, and recorded Markdown output.
Release evidence status and release progress also surface
`.kubeactuary/next-unblock-action-run.json`, so the latest selected blocker
verifier result is visible beside next-task runner status.
They also print the selected next-unblock `nextStep`, so local status output
shows the intended resolution action without opening the JSON artifact.
If a next-unblock verifier already ran and stayed blocked, status keeps the
retry command in `nextUnblockRetry` with a retry condition instead of treating
it as an immediate next command.
Evidence-aware version iteration packs and history status preserve the same
next-unblock action/run and retry-guard metadata, so repeated validation
snapshots keep the selected blocker, verifier result, and retry condition
attached to the local loop.
When a runner fails before the environment probe has run, release evidence
status recommends `prepare_live_evidence_directory.py --probe-environment`
before more live capture attempts.
When the probe classifies the selected task as environment-blocked, status and
progress output print the selected blocker next step and deferred probe retry
condition instead of blocked capture commands. Direct selected-task runner
invocations use the same zero-run
behavior, so a prepared environment-blocked task does not reattempt live
capture until the evidence directory is refreshed after cluster access changes.

The iteration advance helper wraps that runner with before/after version
history recording and reports schema
`kube-actuary.version-iteration-advance.v1`. In run mode it also records the
selected runner status as `.kubeactuary/next-version-task-run.json` and
`.kubeactuary/next-version-task-run.md`, plus the advance workflow status as
`.kubeactuary/version-iteration-advance.json` and
`.kubeactuary/version-iteration-advance.md`. The advance report preserves the
same queue source used by the selected next-task artifact. Each run also
refreshes `.kubeactuary/version-blockers.json` and
`.kubeactuary/version-blockers.md` from the post-run prepared queue, so the
local blocker ledger matches the latest iteration state:

```sh
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir>
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --format markdown
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --version 0.4.3
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --missing-tool kind
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --runnable-only
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --blocked-only
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --run
python3 -B scripts/advance_version_iteration.py <evidence-dir> <history-dir> --probe-environment
```

`prepare_live_evidence_directory.py` and `advance_version_iteration.py` both
accept `--version`, `--capture-status`, `--missing-tool`,
`--environment-status`, `--environment-reason`, `--runnable-only`, and
`--blocked-only`, so the
prepared next-task and before/after history records can stay focused on the
same release version and blocker class.
`advance_version_iteration.py --version <version>` carries that scope through
live evidence directory preparation, selected-task execution, and before/after
history snapshots. They also accept `--probe-environment --kubectl <path>`.
The probe runs only read-only
`kubectl version --client=true` and `kubectl cluster-info` checks. When cluster
access is unavailable, the prepared next-task artifacts record
`blocked-by-environment` instead of pretending the live evidence can be
captured. Probe-blocked advance runs also write a zero-run
`.kubeactuary/next-version-task-run.json` record with `blocked-by-environment`
status, so stale failed runner records do not remain the latest local state.
The advance report also preserves the selected environment blocker status,
next step, and selected next-task worklist drilldown. Probe-blocked runs record
both `before` and `blocked` history snapshots, making the blocked snapshot the
latest version-iteration history entry without running evidence commands. They
also keep the filtered blocker ledger scoped to the selected version and
blocker class.
History status also prints the latest next-task worklist drilldown.
The scaffold also writes
`.kubeactuary/environment-probe.json` with schema
`kube-actuary.environment-probe.v1` for read-only probe details and
`.kubeactuary/environment-blockers.json` with schema
`kube-actuary.environment-blockers.v1`. It also writes
`.kubeactuary/next-unblock-action.json` with schema
`kube-actuary.next-unblock-action.v1`, plus Markdown summaries for local
operators.

Supported evidence schemas:

- `kube-actuary.lightweight-smoke.v1`
- `kube-actuary.helm-smoke.v1`
- `kube-actuary.krew-smoke.v1`
- `kube-actuary.admission-kind-smoke.v1`
- `kube-actuary.managed-kubernetes-smoke.v1`

Provider run evidence means captured output from the target provider or tool,
not a local assumption that the path should work.
