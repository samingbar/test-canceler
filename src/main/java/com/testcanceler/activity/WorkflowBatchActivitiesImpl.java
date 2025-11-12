package com.testcanceler.activity;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;
import io.temporal.activity.Activity;
import io.temporal.client.WorkflowClient;
import io.temporal.api.batch.v1.BatchOperationCancellation;
import io.temporal.api.batch.v1.BatchOperationTermination;
import io.temporal.api.workflowservice.v1.StartBatchOperationResponse;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.api.workflowservice.v1.StartBatchOperationRequest;
import io.temporal.api.batch.v1.BatchOperationCancellation;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.client.WorkflowClientOptions;

import java.util.UUID;
import java.util.logging.Logger;
import java.util.Properties;
import java.io.FileInputStream;
import java.io.IOException;

public class WorkflowBatchActivitiesImpl implements WorkflowBatchActivities {

    private static final Logger logger = Logger.getLogger(WorkflowBatchActivitiesImpl.class.getName());

    @Override
    public void batchCancelWorkflows() {
        // ---- Load API key from .env (same as worker) ----
        Properties props = new Properties();
        try (FileInputStream fis = new FileInputStream(".env")) {
            props.load(fis);
        } catch (IOException e) {
            throw new RuntimeException("Failed to load .env file", e);
        }

        String apiKey = props.getProperty("TEMPORAL_API_KEY_MAIN");
        if (apiKey == null || apiKey.isBlank()) {
            throw new RuntimeException("TEMPORAL_API_KEY_MAIN not found in .env");
        }
        String address = props.getProperty("TEMPORAL_MAIN_ADDRESS");
        if (address == null || address.isBlank()){
            address = "us-east-1.aws.api.temporal.io:7233";
        }
        String namespace = props.getProperty("TEMPORAL_MAIN_NAMESPACE");
        if (namespace==null || namespace.isBlank()){
            throw new RuntimeException("Temporal namespace not found in .env");
        }

        WorkflowServiceStubsOptions serviceOptions = 
            WorkflowServiceStubsOptions.newBuilder()
                .setTarget(address)
                .setEnableHttps(true)
                .addApiKey(() -> apiKey)
                .build();
        
        WorkflowServiceStubs service = WorkflowServiceStubs.newServiceStubs(serviceOptions);
        WorkflowClient client = WorkflowClient.newInstance(
            service,
            WorkflowClientOptions.newBuilder()
                .setNamespace(namespace)
                .build()
            );

        try {
            // Build request
            StartBatchOperationRequest request = StartBatchOperationRequest.newBuilder()
                .setNamespace(namespace)
                .setVisibilityQuery("WorkloadId = \"1\" AND ExecutionStatus = \"Running\"")
                .setJobId(UUID.randomUUID().toString())
                .setReason("Runaway Train")
                .setTerminationOperation(BatchOperationTermination.newBuilder().build()) //Choose between cancelation or termination as appropriate
                .build();

            // Send request via gRPC stub
            StartBatchOperationResponse response = client.getWorkflowServiceStubs().blockingStub().startBatchOperation(request);

            logger.info("Batch cancel response: " + response);

        } catch (Exception e) {
            logger.severe("Batch cancel failed: " + e.getMessage());
            e.printStackTrace();
        }
    }
}