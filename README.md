# Temporal Bulk Cancellation Demo (Test Canceler)

A small Temporal demo that spawns a large number of workflows and then cancels them in bulk. It includes:

- Work service (Python) that creates a high volume of child/grandchild workflows and tags them with a search attribute.
- Canceler service (Python) that orchestrates cancellation and confirmation.
- Batch worker (Java) that calls the Temporal service batch operation API (activity on a separate task queue).

Use this project to experiment with high‑volume workflow creation and mass cancellation strategies on Temporal Cloud.

---

## Architecture

- Work service (Python):
  - Task queue `work-task-queue`.
  - Workflow `CancelableWorkflow` spawns many `ChildWorkflow` instances.
  - All workflows upsert search attribute `WorkloadId = "1"` by default.

- Canceler service (Python):
  - Task queue `canceler-task-queue`.
  - Workflow `BulkCancelWorkflow` coordinates cancellation:
    1) Triggers a Java activity `batch_cancel_workflows` on task queue `batch-queue`.
    2) Loops to find new workflows started after the batch request time and terminates them in parallel.
    3) Polls until no matching workflows remain running.
  - Uses an oversize payload codec that writes large payloads under `/tmp/payloads`.

- Batch worker (Java):
  - Task queue `batch-queue`.
  - Activity `batch_cancel_workflows` issues a service batch termination with a visibility query.

Namespace topology:
- "Main" namespace hosts the high‑volume workflows (work service).
- "Canceler" namespace hosts the canceler workflow and the Java activity worker that polls `batch-queue`.
- The Java activity implementation connects to the main namespace when issuing StartBatchOperation so it can target the spawned workflows. Ensure both namespaces are correctly set in `.env` and in the Java worker if you change defaults.

---

## Repository Layout

```
src/
  work/
    activity.py           # generate_uuid activity
    workflow.py           # CancelableWorkflow (parent) + ChildWorkflow
    worker.py             # Work service worker (task queue: work-task-queue)
    run.py                # Starts a CancelableWorkflow instance
    cancel.py             # Sends cancel signal to the parent workflow (optional)
    config.py             # Work service config (reads from .env)

  canceler/
    activity.py           # query, bulk terminate, confirm
    workflow.py           # BulkCancelWorkflow orchestration
    worker.py             # Canceler worker (task queue: canceler-task-queue)
    run.py                # Starts BulkCancelWorkflow
    payload_manager.py    # Simple oversize payload codec (/tmp/payloads)
    config.py             # Canceler service config (reads from .env)

main Java sources (batch worker)
  src/main/java/com/testcanceler/
    worker/WorkerStarter.java               # Starts worker on task queue "batch-queue"
    activity/WorkflowBatchActivities.java   # Activity interface
    activity/WorkflowBatchActivitiesImpl.java# Activity implementation (batch termination)

gradle/ build files
  build.gradle, settings.gradle, gradlew*
  app/           # Unrelated sample Gradle app

pyproject.toml   # Python deps
.env             # Environment variables (fill with your own values)
```

Key Python:

- `src/work/workflow.py` – Spawns load and adds `WorkloadId` search attribute.
- `src/canceler/workflow.py` – Batch trigger → new‑workflows cleanup → confirm loop.
- `src/canceler/activity.py` – Query, parallel terminate, and confirm helpers.

Key Java:

- `src/main/java/com/testcanceler/worker/WorkerStarter.java` – Starts the batch activity worker.
- `src/main/java/com/testcanceler/activity/WorkflowBatchActivitiesImpl.java` – Calls StartBatchOperation with a visibility query.

---

## Requirements

- Python 3.13 (see `.python-version`).
- Java 21 and Gradle (wrapper included).
- Temporal Cloud namespace and API keys.

Install Python dependencies with uv or pip:

```
# Using uv
uv venv
source .venv/bin/activate
uv pip install -e .

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Configuration

This repo centralizes most settings in Python via `src/work/config.py` and `src/canceler/config.py`, which read from `.env`.

Set these variables in `.env` at the repo root:

- Work service (Python):
  - `TEMPORAL_MAIN_ADDRESS` – e.g., `us-east-1.aws.api.temporal.io:7233`
  - `TEMPORAL_MAIN_NAMESPACE` – your namespace for spawning workflows
  - `TEMPORAL_MAIN_TASK_QUEUE` – e.g., `work-task-queue`
  - `TEMPORAL_API_KEY_MAIN` – API key with access to the above namespace

- Canceler service (Python):
  - `TEMPORAL_CANCELER_ADDRESS` – usually same as main address
  - `TEMPORAL_CANCELER_NAMESPACE` – namespace where canceler workflow runs (often same as main)
  - `TEMPORAL_CANCELER_TASK_QUEUE` – e.g., `canceler-task-queue`
  - `TEMPORAL_API_KEY_CANCELER` – API key for the canceler

- Optional tuning:
  - `CANCEL_CONCURRENCY` – max parallel terminates (default 750)
  - `CONFIRM_TIMEOUT_SECONDS` – confirm loop timeout (default 240)
  - `CONFIRM_POLL_SECONDS` – confirm loop poll interval (default 5)
  These are set in the config files located inside the work and canceler packages. 

Notes:

- The Java activity and Python canceler must target the same Temporal namespace as the spawned workloads (typically the "main" namespace) for visibility queries and terminations to succeed.
- Search attribute used is a keyword `WorkloadId` with default value "1"; adjust in `src/work/config.py` (`WORKLOAD_ID_VALUE`) and ensure Java/Python queries match.
- The `.env` committed here contains example keys; replace with your own and avoid committing secrets.

Payload codec:

- `src/canceler/payload_manager.py` stores large payloads under `/tmp/payloads`. Create the directory if needed: `mkdir -p /tmp/payloads`.

---

## Quick Start

1) Prepare environment

```
cp .env .env.local  # optional copy; edit values
source .venv/bin/activate
```

2) Start the Python work worker (terminal A)

```
python src/work/worker.py
```
3) Start the workflow snowball. This can grow as large as 2M+ workflows. (terminal B)

```
python src/work/run.py
# Starts parent CancelableWorkflow with many children/grandchildren on work-task-queue
```

4) Start the Java batch worker (terminal C)

```
./gradlew build
./gradlew run
```

After this step, wait for the workflow execution snowball to grow as large as you'd like. 

5) Start the Python canceler worker (terminal D)

```
python src/canceler/worker.py
```

6) Start the cancellation orchestration (terminal E)

```
python src/canceler/run.py
# Triggers Java batch cancel, cleans up new workflows, confirms all canceled
```

---

## How It Works

- Work service
  - `CancelableWorkflow` spawns many `ChildWorkflow` instances with concurrency control and `ParentClosePolicy.TERMINATE`.
  - Each child upserts `WorkloadId` to enable query‑based targeting.

- Canceler service
  - Kicks off `batch_cancel_workflows` (Java activity on `batch-queue`) which issues a StartBatchOperation with a visibility query (by default `WorkloadId = "1" AND ExecutionStatus = "Running"`).
  - Tracks the batch start time and repeatedly executes `query_new_wf_executions` to find workflows with `StartTime >= batchStartTime` and the same `WorkloadId`, then calls `bulk_cancel_workflows` to terminate them in parallel.
  - Calls `confirm_all_canceled` to poll until no running workflows remain for the `WorkloadId`.

---

## Troubleshooting

- No workflows found: ensure all workers/clients share the same namespace and `WorkloadId` value.
- 429/rate limiting: lower `CANCEL_CONCURRENCY`.
- Confirmation never finishes: increase `CONFIRM_TIMEOUT_SECONDS` and verify your visibility query matches status + attribute value.
- Payload codec errors: ensure `/tmp/payloads` exists and is writable.

---

## Notes and TODOs

- Namespaces are hard‑coded in several files; unify them or switch to reading from `.env` for all clients/workers.
- Java `WorkerStarter` currently hard‑codes the canceler namespace; consider reading it from `.env` like the activity implementation does for the main namespace.
- Some concurrency settings in Python workers are set very high for laptop demos; tune down for real environments.
- `track_batch` in `src/canceler/activity.py` is a WIP and not wired.
- Consider adding `.env` to `.gitignore` and rotating any committed secrets.

---

## License

No license specified.
