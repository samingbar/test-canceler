from __future__ import annotations
import os
from dotenv import load_dotenv
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from workflow import BulkCancelWorkflow
from activity import query_new_wf_executions, confirm_all_canceled, bulk_cancel_workflows
#from activity import batch_cancel_workflows #excluded for now due to lack of python report
from payload_manager import Codec
from temporalio.converter import DataConverter, DefaultPayloadConverter
PAYLOAD_PATH = "/tmp/payloads"
codec = Codec(path=PAYLOAD_PATH, min_bytes=1_000_000)  # tune threshold as needed
from config import TEMPORAL_CANCELER_ADDRESS,TEMPORAL_CANCELER_API_KEY,TEMPORAL_CANCELER_TASK_QUEUE,TEMPORAL_CANCELER_NAMESPACE

interrupt_event = asyncio.Event()

data_converter = DataConverter(
    payload_converter_class=DefaultPayloadConverter,
    payload_codec=codec,
)

async def main():
    # Connect to Temporal Server. Change address if needed for your demo.
    # Initialize client connection
    client = await Client.connect(
        TEMPORAL_CANCELER_ADDRESS,
        namespace=TEMPORAL_CANCELER_NAMESPACE,
        api_key=TEMPORAL_CANCELER_API_KEY,
        tls=True,
        data_converter=data_converter
    )

    async with Worker(
        client,
        task_queue=TEMPORAL_CANCELER_TASK_QUEUE,
        workflows=[BulkCancelWorkflow],
        activities=[query_new_wf_executions, confirm_all_canceled, bulk_cancel_workflows], # Batch Cancel Workflows is excluded
        max_cached_workflows = 10000,
        max_concurrent_workflow_tasks = 1000
    ):
        # Keep the worker alive until interrupted (Ctrl+C during demos)
        await interrupt_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
