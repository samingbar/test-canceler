import os
from dotenv import load_dotenv
import asyncio
from temporalio.client import Client
from workflow import BulkCancelWorkflow
from config import TEMPORAL_CANCELER_TASK_QUEUE, TEMPORAL_CANCELER_ADDRESS, TEMPORAL_CANCELER_NAMESPACE, TEMPORAL_CANCELER_API_KEY


async def main() -> None:
    interrupt_event = asyncio.Event()
    
    # Connect to Temporal server
    client = await Client.connect(
        TEMPORAL_CANCELER_ADDRESS,
        namespace=TEMPORAL_CANCELER_NAMESPACE,
        api_key=TEMPORAL_CANCELER_API_KEY,
        tls=True,
    )

    workflow_id = f"canceler-workflow"
    handle = await client.start_workflow(
        BulkCancelWorkflow.run, 
        id=workflow_id,
        task_queue=TEMPORAL_CANCELER_TASK_QUEUE,
    )

    print(f"Started workflow {workflow_id}")

    try:
        await handle.result()
        print("Workflow completed after cancellation.")
    except Exception as exc:
        print(f"Workflow finished with exception: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
