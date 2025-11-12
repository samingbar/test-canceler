from datetime import timedelta 
from temporalio.common import RetryPolicy
import os
from dotenv import load_dotenv
from temporalio.workflow import ParentClosePolicy


load_dotenv()

#Namespace Values
TEMPORAL_CANCELER_API_KEY = os.getenv("TEMPORAL_API_KEY_CANCELER")
TEMPORAL_MAIN_API_KEY = os.getenv('TEMPORAL_API_KEY_MAIN')
TEMPORAL_MAIN_NAMESPACE=os.getenv('TEMPORAL_MAIN_NAMESPACE')
TEMPORAL_CANCELER_NAMESPACE=os.getenv('TEMPORAL_CANCELER_NAMESPACE')
TEMPORAL_MAIN_TASK_QUEUE=os.getenv('TEMPORAL_MAIN_TASK_QUEUE')
TEMPORAL_CANCELER_TASK_QUEUE=os.getenv('TEMPORAL_CANCELER_TASK_QUEUE')
TEMPORAL_MAIN_ADDRESS=os.getenv("TEMPORAL_MAIN_ADDRESS", "us-east-1.aws.api.temporal.io:7233")
TEMPORAL_CANCELER_ADDRESS = os.getenv("TEMPORAL_CANCELER_ADDRESS", "us-east-1.aws.api.temporal.io:7233")

#Target Jobs
WORKLOAD_ID = 1 #Target search attribute value

# Spawning Settings (Only affects the 'work' workflow)
PARENT_CLOSE_POLICY = ParentClosePolicy.TERMINATE  # Consider ABANDON/REQUEST_CANCEL as needed
CHILD_SPAWN_SEMAPHORE = 100
WORKLOAD_ID_ATTR_NAME = "WorkloadId"
WORKLOAD_ID_VALUE = "1"

# Timeouts & polling defaults
QUERY_TIMEOUT = timedelta(minutes=10)
CANCEL_TIMEOUT = timedelta(minutes=25)
CONFIRM_TIMEOUT = timedelta(minutes=15)
POLL_INTERVAL = timedelta(seconds=5)
MAX_POLLS = 60  # upper bound to avoid infinite polling

# Conservative retries; let StartToClose be the ultimate bound.
DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_attempts=0,  # unlimited attempts until StartToClose
)
