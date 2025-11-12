from __future__ import annotations
import os
import logging
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from workflow import CancelableWorkflow, ChildWorkflow
from activity import generate_uuid
from config import TEMPORAL_MAIN_NAMESPACE, TEMPORAL_MAIN_ADDRESS, TEMPORAL_MAIN_API_KEY, TEMPORAL_MAIN_TASK_QUEUE
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

interrupt_event = asyncio.Event()

async def main():
    # Connect to Temporal Server. Change address to yoru appropriate address.
    # Initialize client connection
    client = await Client.connect(
        TEMPORAL_MAIN_ADDRESS,
        namespace=TEMPORAL_MAIN_NAMESPACE,
        api_key=TEMPORAL_MAIN_API_KEY,
        tls=True,
    )

    print("Starting worker process...")

    async with Worker(
        client,
        task_queue=TEMPORAL_MAIN_TASK_QUEUE,
        workflows=[CancelableWorkflow, ChildWorkflow],
        activities=[generate_uuid],
        max_cached_workflows = 10000, #This settings is set unreasonably high in an attempt to eek the most out of a few workers running on my laptop. I don't recommend keeping these settings long term.
        max_concurrent_workflow_tasks = 1000 #This settings is set unreasonably high in an attempt to eek the most out of a few workers running on my laptop. I don't recommend keeping these settings long term.
    ):
        # Keep the worker alive until interrupted (Ctrl+C during demos)
        await interrupt_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
