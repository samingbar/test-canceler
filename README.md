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

  canceler/
    activity.py           # query, bulk terminate, confirm
    workflow.py           # BulkCancelWorkflow orchestration
    worker.py             # Canceler worker (task queue: canceler-task-queue)
    run.py                # Starts BulkCancelWorkflow
    payload_manager.py    # Simple oversize payload codec (/tmp/payloads)

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

Define these in `.env` at repo root:

- `TEMPORAL_ADDRESS` – e.g., `us-east-1.aws.api.temporal.io:7233`
- `TEMPORAL_NAMESPACE` – your Temporal Cloud namespace
- `TEMPORAL_API_KEY_MAIN` – API key for the work service
- `TEMPORAL_API_KEY_CANCELER` – API key for the canceler/batch services
- Optional tuning:
  - `CANCEL_CONCURRENCY` – max parallel cancels (default 750)
  - `CONFIRM_TIMEOUT_SECONDS` – confirm loop timeout (default 240)
  - `CONFIRM_POLL_SECONDS` – confirm loop poll interval (default 5)

Important consistency notes:

- Several files currently hard‑code `address`/`namespace`. Ensure they match your `.env` values or update them:
  - Python workers/clients: `src/work/worker.py`, `src/work/run.py`, `src/work/cancel.py`, `src/canceler/worker.py`, `src/canceler/run.py`
  - Java worker/activity: `src/main/java/com/testcanceler/worker/WorkerStarter.java`, `src/main/java/com/testcanceler/activity/WorkflowBatchActivitiesImpl.java`
- The `.env` included here has example keys. Replace with your own secrets and avoid committing them.

Search attribute:

- Uses keyword attribute `WorkloadId` (default value "1"). Adjust in `src/work/workflow.py` and in canceler queries in `src/canceler/activity.py`.

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

3) Start the Java batch worker (terminal B)

```
./gradlew run
```

4) Start the Python canceler worker (terminal C)

```
python src/canceler/worker.py
```

5) Launch the spawning workflow (terminal D)

```
python src/work/run.py
# Starts parent CancelableWorkflow with many children/grandchildren on work-task-queue
```

6) Start the cancellation orchestration (terminal E)

```
python src/canceler/run.py
# Triggers Java batch cancel, cleans up new workflows, confirms all canceled
```

Optional: send a direct cancel signal to the parent

```
python src/work/cancel.py
```

---

## How It Works

- Work service
  - `CancelableWorkflow` spawns many `ChildWorkflow` instances with concurrency control and `ParentClosePolicy.TERMINATE`.
  - Each child upserts `WorkloadId` to enable query‑based targeting.

- Canceler service
  - Kicks off `batch_cancel_workflows` (Java activity on `batch-queue`) using a visibility query like `WorkloadId = "1" AND ExecutionStatus = "Running"`.
  - Lists any new workflows started after the batch request time and terminates them in parallel.
  - Polls until no running workflows remain for the `WorkloadId`.

---

## Troubleshooting

- No workflows found: ensure all workers/clients share the same namespace and `WorkloadId` value.
- 429/rate limiting: lower `CANCEL_CONCURRENCY`.
- Confirmation never finishes: increase `CONFIRM_TIMEOUT_SECONDS` and verify your visibility query matches status + attribute value.
- Payload codec errors: ensure `/tmp/payloads` exists and is writable.

---

## Notes and TODOs

- Namespaces are hard‑coded in several files; unify them or switch to reading from `.env` for all clients/workers.
- Some concurrency settings in Python workers are set very high for laptop demos; tune down for real environments.
- `track_batch` in `src/canceler/activity.py` is a WIP and not wired.
- Consider adding `.env` to `.gitignore` and rotating any committed secrets.

---

## License

No license specified.

