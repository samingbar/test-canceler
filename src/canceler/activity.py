from __future__ import annotations
import uuid
import os
import asyncio
from typing import List
from dotenv import load_dotenv
from temporalio import activity
from temporalio.client import Client
from temporalio.api.workflowservice.v1 import StartBatchOperationRequest
from temporalio.api.batch.v1 import BatchOperationCancellation, BatchOperationTermination
from temporalio.api.enums.v1 import BatchOperationState
from temporalio.api.workflowservice.v1 import StartBatchOperationRequest, DescribeBatchOperationRequest
from temporalio.exceptions import ApplicationError
from config import TEMPORAL_MAIN_API_KEY, TEMPORAL_MAIN_NAMESPACE, TEMPORAL_MAIN_ADDRESS

_CLIENT_CACHE: Client | None = None

async def _get_client() -> Client:
    global _CLIENT_CACHE
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE

    api_key = TEMPORAL_MAIN_API_KEY
    address = TEMPORAL_MAIN_ADDRESS
    namespace = TEMPORAL_MAIN_NAMESPACE
    print(api_key, address, namespace)
    if not api_key:
        raise RuntimeError("TEMPORAL_API_KEY_MAIN is required to connect to Temporal Cloud")

    _CLIENT_CACHE = await Client.connect(
        address,
        namespace=namespace,
        api_key=api_key,
        tls=True,
    )
    return _CLIENT_CACHE

#This activity checks for any workflow exeuctions spawned after the start of the batch job
@activity.defn
async def query_new_wf_executions(workload_id: int, timestamp) -> List[str]:
    client = await _get_client()
    # Query running workflows that match the WorkloadId search attribute
    query = f'WorkloadId = "{workload_id}" AND ExecutionStatus = "Running" AND `StartTime`>="{timestamp}"'
    ids: List[str] = []
    async for wf in client.list_workflows(query=query):
        # wf has execution.workflow_id and run_id
        print(wf.id)
        ids.append(wf.id)
    return ids

#This batch cancler function is not currently supported in the python SDK, take a look at the implementation in Java under the app folder. 
"""@activity.defn
async def batch_cancel_workflows() -> None:
    client = await _get_client()
    print("workflow_service has:", hasattr(client.workflow_service, "start_batch_operation"))
    print("operator_service has:", hasattr(client.operator_service, "start_batch_operation"))

    request = StartBatchOperationRequest(
        namespace=client.namespace,
        visibility_query= 'WorkloadId = "1" AND ExecutionStatus = "Running"',
        job_id = str(uuid.uuid4()),
        reason="Runaway Train",
        cancellation_operation = BatchOperationCancellation()
    )
    response = await client.workflow_service.start_batch_operation(request)

    activity.logger.info(response)
    return response"""

#A sample activity for tracking batch execution(s); Not currently utilized by the workflow. 
"""@activity.defn
async def track_batch(jobId:str):
    client = _get_client()

    while True:
        response = await client.workflow_service.describe_batch_operation({
        'jobId': jobId, 
        'namespace': 'default'
        })

        activity.logger.info(f"Cancelation Status Update -- Status = {response}")

        if response.state == BatchOperationState.BATCH_OPERATION_STATE_FAILED:
            raise Error('Failed to cleanup workflows in tests')
    
        if response.state == BatchOperationState.BATCH_OPERATION_STATE_RUNNING:
            asyncio.sleep(120)
            continue
        if response.state == BatchOperationState.BATCH_OPERATION_STATE_COMPLETED:
            return True
        else:
            raise ApplicationError("Error: Unexpected Batch Process State")
"""
#Bulk cancelataion of workflow executions using semaphor
@activity.defn
async def bulk_cancel_workflows(workflow_ids: List[str]) -> int:
    client = await _get_client()
    # Fire off cancellations in parallel with some throttling
    sem = asyncio.Semaphore(int(os.getenv("CANCEL_CONCURRENCY", "750")))

    async def cancel_one(wf_id: str) -> bool:
        async with sem:
            try:
                handle = client.get_workflow_handle(workflow_id=wf_id)
                await handle.terminate()
                return True
            except Exception:
                return False

    results = await asyncio.gather(*(cancel_one(wf_id) for wf_id in workflow_ids))
    return sum(1 for ok in results if ok)

#This activity checks whether all activities have been canceled for a certain amount of time and returns the outcome
@activity.defn
async def confirm_all_canceled(workload_id: int) -> bool:
    client = await _get_client()
    # Poll until there are no running workflows with the workload_id
    # Give up after a timeout window
    deadline_seconds = int(os.getenv("CONFIRM_TIMEOUT_SECONDS", "240"))
    poll_interval = float(os.getenv("CONFIRM_POLL_SECONDS", "5"))

    async def any_running() -> bool:
        query = f"WorkloadId = {workload_id} and ExecutionStatus = 'Running'"
        async for _ in client.list_workflows(query=query):
            return True
        return False

    remaining = deadline_seconds
    while remaining > 0:
        if not await any_running():
            return True
        await asyncio.sleep(poll_interval)
        remaining -= poll_interval
    return False
