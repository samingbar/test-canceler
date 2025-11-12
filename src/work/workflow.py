from temporalio import workflow
from temporalio.workflow import ParentClosePolicy
from temporalio.common import (
    TypedSearchAttributes,
    SearchAttributeKey,
    SearchAttributePair,
)
from datetime import timedelta
import asyncio
from activity import generate_uuid

from config import PARENT_CLOSE_POLICY, CHILD_SPAWN_SEMAPHORE, WORKLOAD_ID_ATTR_NAME, WORKLOAD_ID_VALUE, TEMPORAL_MAIN_TASK_QUEUE

# ------------------------------- Parent ------------------------------------
@workflow.defn
class CancelableWorkflow:
    """Launch a batch of child workflows and wait for them to close.

    Signals:
        cancel: Emergency cancel that cascades to direct children.
    """

    def __init__(self) -> None:
        # State
        self._cancelled: bool = False
        self.spawn: bool = True
        self.children: list[workflow.ChildWorkflowHandle] = []
        self.sem = asyncio.Semaphore(CHILD_SPAWN_SEMAPHORE)
        self.workload_id_key = SearchAttributeKey.for_keyword(WORKLOAD_ID_ATTR_NAME)

    # ---- helpers ----
    @staticmethod
    async def _wait_closed(h: workflow.ChildWorkflowHandle) -> None:
        """Wait for a child workflow to close, swallowing errors."""
        try:
            await h.result()
        except Exception:
            # Intentionally ignore, e.g. if terminated/cancelled
            pass

    async def _start_one(self, n: int, spawn: bool, search_attributes = None) -> workflow.ChildWorkflowHandle:
        """Start a single child workflow with concurrency control."""
        async with self.sem:

            # Generate a unique workflow id via activity
            wfid = await workflow.execute_activity(
                generate_uuid, start_to_close_timeout=timedelta(seconds=60)
            )

            # Start the child
            handle = await workflow.start_child_workflow(
                ChildWorkflow.run,
                args=(n, spawn),
                id=f"workflow-{wfid}",
                task_queue=TEMPORAL_MAIN_TASK_QUEUE,
                search_attributes=search_attributes,
                parent_close_policy=PARENT_CLOSE_POLICY,
            )
            
            workflow.logger.info(f"Started child workflow {n} -> {handle.id}")
            self.children.append(handle)
            return handle

    async def _backup_cancel_by_index(self, idx: int) -> None:
        """Emergency cancel of a direct child via signal (no parent cancel)."""
        child = self.children[idx]
        await child.signal(ChildWorkflow.cancel)

    # ---- entrypoints ----
    @workflow.run
    async def run(self, executions: int = 2000) -> None:
        workflow.logger.info("Starting parent workflow...")
        
        # Create search attributes for spawning
        search_attributes = TypedSearchAttributes([SearchAttributePair(self.workload_id_key, WORKLOAD_ID_VALUE)])
        workflow.logger.info("Starting workflow spawning...")

        while not self._cancelled:
            if self.spawn:
                # Launch children
                await asyncio.gather(*[self._start_one(n, True, search_attributes) for n in range(executions)])

                # Wait for all to finish/close
                await asyncio.gather(
                    *[self._wait_closed(h) for h in self.children],
                    return_exceptions=True,
                )
                self.spawn = False
                workflow.logger.info("Finishing workflow spawning...") 
            workflow.logger.info("Completed child workflows. Workflow waiting…")
            await workflow.sleep(timedelta(minutes=30))

        workflow.logger.info("Parent workflow cancelled.")

    @workflow.signal
    async def cancel(self) -> None:
        # Send cancel signal to each direct child as an emergency cancel. Used during early testing.
        await asyncio.gather(
            *[self._backup_cancel_by_index(i) for i in range(len(self.children))],
            return_exceptions=True,
        )
        self._cancelled = True
        


# ------------------------------- Child -------------------------------------
@workflow.defn
class ChildWorkflow:
    """Child workflow that can optionally spawn further children and/or loop."""

    def __init__(self) -> None:
        self.id: int | None = None
        self._cancelled: bool = False
        self.spawn: bool = True
        self.children: list[workflow.ChildWorkflowHandle] = []
        self.sem = asyncio.Semaphore(CHILD_SPAWN_SEMAPHORE)
        self.workload_id_key = SearchAttributeKey.for_keyword(WORKLOAD_ID_ATTR_NAME)

    async def _start_one(self, n: int, spawn: bool = False, search_attributes = None) -> workflow.ChildWorkflowHandle:
        """Start a grandchild workflow with concurrency control."""
        async with self.sem:
            wfid = await workflow.execute_activity(
                generate_uuid, start_to_close_timeout=timedelta(seconds=60)
            )
            handle = await workflow.start_child_workflow(
                ChildWorkflow.run,
                args=(n, spawn),
                id=f"workflow-{wfid}",
                task_queue=TEMPORAL_MAIN_TASK_QUEUE,
                search_attributes=search_attributes,
                parent_close_policy=PARENT_CLOSE_POLICY,
            )
            workflow.logger.info(f"[child {self.id}] started grandchild {n} -> {handle.id}")
            self.children.append(handle)
            return handle

    @workflow.run
    async def run(self, id: int, spawn: bool) -> None:
        self.id = id
        workflow.logger.info(f"Child workflow {self.id} started.")

        # Create search attributes for spawning
        search_attributes = TypedSearchAttributes([SearchAttributePair(self.workload_id_key, WORKLOAD_ID_VALUE)])

        while not self._cancelled:
            self.spawn = spawn
            if self.spawn:
                # Launch grandchildren and wait for their completion/closure
                await asyncio.gather(*[self._start_one(n, False, search_attributes) for n in range(500)])
                await asyncio.gather(
                    *[CancelableWorkflow._wait_closed(h) for h in self.children],
                    return_exceptions=True,
                )
                self.spawn = False
            else:
                workflow.logger.info("Spawning complete, workflow waiting…")
                await workflow.sleep(timedelta(minutes=30))

    @workflow.signal
    def cancel(self) -> None:
        self._cancelled = True
        workflow.logger.info(f"Child workflow {self.id} received cancel signal.")
