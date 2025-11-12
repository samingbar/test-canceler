from temporalio import activity
import uuid

@activity.defn
async def generate_uuid():
    new_id = uuid.uuid4()
    return new_id