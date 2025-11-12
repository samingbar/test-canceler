import os
import asyncio
from temporalio.client import Client
from workflow import CancelableWorkflow
from temporalio.common import (
    TypedSearchAttributes,
    SearchAttributeKey,
    SearchAttributePair,
)
from config import TEMPORAL_MAIN_API_KEY, TEMPORAL_MAIN_ADDRESS, TEMPORAL_MAIN_NAMESPACE, TEMPORAL_MAIN_TASK_QUEUE

#Use this script to kick off a spawning workflow. 
async def main() -> None:
    interrupt_event = asyncio.Event()

    search_attributes = TypedSearchAttributes([SearchAttributePair(SearchAttributeKey.for_keyword("WorkloadId"), "1")])
    
    # Connect to Temporal server
    client = await Client.connect(
        TEMPORAL_MAIN_ADDRESS,
        namespace=TEMPORAL_MAIN_NAMESPACE,
        api_key=TEMPORAL_MAIN_API_KEY,
        tls=True
    )

    # Start the CancelableWorkflow;
    workflow_id = f"cancelable-workflow"
    handle = await client.start_workflow(
        CancelableWorkflow.run, 
        2000,
        id=workflow_id,
        search_attributes=search_attributes,
        task_queue=TEMPORAL_MAIN_TASK_QUEUE,
    )

    print(f"Started workflow {workflow_id}")

    try:
        await handle.result()
        print("Workflow completed after cancellation.")
    except Exception as exc:
        print(f"Workflow finished with exception: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
