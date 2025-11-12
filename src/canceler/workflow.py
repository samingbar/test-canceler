from __future__ import annotations

from datetime import timedelta
from typing import Sequence

from temporalio import workflow
from config import QUERY_TIMEOUT, CANCEL_TIMEOUT, CONFIRM_TIMEOUT,POLL_INTERVAL,MAX_POLLS,DEFAULT_RETRY, WORKLOAD_ID
@workflow.defn
class BulkCancelWorkflow:
    """
    Queries for running workflows by workload_id, issues bulk cancels, then polls
    until all are confirmed canceled (or we hit MAX_POLLS).
    """
    def __init__(self):
        self.fully_canceled = False

    @workflow.run
    async def run(self, workload_id: int = WORKLOAD_ID, poll_interval: timedelta = POLL_INTERVAL, max_polls: int = MAX_POLLS):
        logger = workflow.logger
        logger.info("Starting termination process...")

        #Begin Workflow Logic 
        
        #First, we will kick off the batch job using an activity:
        batch_job_id = await workflow.execute_activity(
                        "batch_cancel_workflows",
                        task_queue="batch-queue",
                        start_to_close_timeout=CANCEL_TIMEOUT,
                        retry_policy=DEFAULT_RETRY,
                        )
        batch_start_time = workflow.now() #We want to capture the time that we triggered the batch job in order to re-use it for the query in our cleanup system 
        workflow.logger.info(f"Requested batch cancel for relevant workflows at {batch_start_time}")

        #Second, we will track the progress of our batch job and run interim cancelations on any workflows spawned while we are waiting
        while not self.fully_canceled:
                for attempt in range(1,MAX_POLLS+1):
                # 1) Check for new workflow executions that have spawned
                    timestamp = batch_start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" 
                    workflow_ids: Sequence[str] = await workflow.execute_activity(
                        "query_new_wf_executions",
                        args =(workload_id, timestamp),
                        start_to_close_timeout=QUERY_TIMEOUT,
                        retry_policy=DEFAULT_RETRY,
                        )
                    # 2A) If new workflows have spawned since triggering the batch job, we will send requests to have them terminated. 
                    if workflow_ids:
                        canceled = await workflow.execute_activity(
                            "bulk_cancel_workflows",
                            workflow_ids,
                            start_to_close_timeout=CANCEL_TIMEOUT,
                            retry_policy=DEFAULT_RETRY,
                        )
                        canceled = int(canceled or 0)
                        workflow.logger.info("Requested cancel for %d workflows", canceled)

                    # 2B) Log that there are no new workflows to cancel
                    else:
                        workflow.logger.info("No new workflows found for workload_id=%s", workload_id)

                    # 3) Poll for some time to see if all of the workflows are canceled
                    
                        confirmed = await workflow.execute_activity(
                            "confirm_all_canceled",
                            workload_id,
                            start_to_close_timeout=CONFIRM_TIMEOUT,
                            retry_policy=DEFAULT_RETRY,
                        )
                        # 3A) If there are no more jobs picked up by the query, then end the loop
                        if confirmed:
                            self.fully_canceled = True
                            workflow.logger.info("All workflows confirmed canceled after %d polls", attempt)
                            response = "Cancelation Successful"

                        # 3B) Otherwise, continue the loop
                        else:
                            workflow.logger.info(
                                "Not yet fully canceled (attempt %d/%d); sleeping %ss",
                                attempt,
                                max_polls,
                                int(poll_interval.total_seconds()),
                            )
                            await workflow.sleep(poll_interval)
        
        return response
