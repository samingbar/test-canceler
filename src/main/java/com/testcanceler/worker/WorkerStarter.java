package com.testcanceler.worker;

import io.grpc.netty.shaded.io.grpc.netty.GrpcSslContexts;
import io.grpc.ClientInterceptor;
import io.grpc.Metadata;
import io.grpc.stub.MetadataUtils;
import io.temporal.client.WorkflowClient;
import io.temporal.common.converter.DataConverter;
import io.temporal.payload.codec.PayloadCodec;
//import io.temporal.payload.codec.PayloadCodecChain;
import io.temporal.payload.codec.ZlibPayloadCodec;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.worker.Worker;
import io.temporal.worker.WorkerFactory;
import io.temporal.client.WorkflowClientOptions;

import com.testcanceler.activity.WorkflowBatchActivitiesImpl;


import java.io.FileInputStream;
import java.io.IOException;
import java.util.Collections;
import java.util.Properties;
import java.util.Map;

public class WorkerStarter {

    public static void main(String[] args) throws IOException {
        // Load .env (equivalent to dotenv in Python)
        Properties props = new Properties();
        try (FileInputStream fis = new FileInputStream(".env")) {
            props.load(fis);
        }
        //Grab API Key
        String apiKey = props.getProperty("TEMPORAL_API_KEY_CANCELER");
        if (apiKey == null || apiKey.isEmpty()) {
            throw new RuntimeException("TEMPORAL_API_KEY_CANCELER not set in .env");
        }
        System.out.println(apiKey);

        // Configure Temporal Cloud connection
        WorkflowServiceStubsOptions serviceOptions = 
            WorkflowServiceStubsOptions.newBuilder()
                .setTarget("us-east-1.aws.api.temporal.io:7233")
                .setEnableHttps(true)
                .addApiKey(() -> apiKey)
                .build();

        WorkflowServiceStubs service = WorkflowServiceStubs.newServiceStubs(serviceOptions);

        // Create a client for the given namespace
        WorkflowClientOptions clientOptions = WorkflowClientOptions.newBuilder()
                    .setNamespace("canceler-test.a2dd6")
                    .build();

        WorkflowClient client = WorkflowClient.newInstance(service, clientOptions);


        // Create worker factory
        WorkerFactory factory = WorkerFactory.newInstance(client);

        // Register a worker on the same queue as your Python version
        Worker worker = factory.newWorker("batch-queue");

        // Register your workflow and activities
        worker.registerActivitiesImplementations(new WorkflowBatchActivitiesImpl());

        // Configure advanced options (like max concurrency) using WorkerOptions if desired
        // e.g. WorkerOptions.newBuilder().setMaxConcurrentWorkflowTaskExecutionSize(1000).build();

        // Start polling
        factory.start();

        System.out.println("✅ Worker started for task queue: batch-queue");
        System.out.println("Press Ctrl+C to stop...");

        // Keep running indefinitely (like asyncio.Future.wait())
        try {
            Thread.currentThread().join();
        } catch (InterruptedException e) {
            System.out.println("Worker interrupted, shutting down...");
            factory.shutdown();
        }
    }
}

