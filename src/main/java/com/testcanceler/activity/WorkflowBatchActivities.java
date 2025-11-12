package com.testcanceler.activity;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;


@ActivityInterface
public interface WorkflowBatchActivities {
    @ActivityMethod(name="batch_cancel_workflows")
    void batchCancelWorkflows();
}