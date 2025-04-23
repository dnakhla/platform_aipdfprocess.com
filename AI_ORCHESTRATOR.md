# AI Orchestration Service Specification

## Overview

The AI Orchestrator is the intelligent coordinator that:
1. Interprets user requests about PDF processing
2. Determines the sequence of PDF operations needed
3. Executes these operations by calling the appropriate Lambda functions
4. Evaluates results and decides on follow-up actions
5. Delivers the final processed document to the user

## Architecture

```
┌────────────────┐     ┌───────────────────┐     ┌─────────────────┐
│ API Gateway    │────►│ AI Orchestrator   │────►│ LLM Service     │
└────────────────┘     └─────────┬─────────┘     └─────────────────┘
                                 │                         ▲
                                 ▼                         │
                       ┌─────────────────┐                 │
                       │ DynamoDB        │                 │
                       │ (Job State)     │                 │
                       └─────────────────┘                 │
                                 │                         │
                                 ▼                         │
┌────────────────┐     ┌─────────────────┐                 │
│ Input S3       │────►│ PDF Functions   │─────────────────┘
└────────────────┘     └─────────────────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ Output S3       │
                       └─────────────────┘
```

## Implementation Components

### 1. Request Handler

```javascript
/**
 * Orchestrator Lambda Handler
 * 
 * @param {Object} event - API Gateway or direct invocation event
 * @param {string} event.pdfUrl - URL to PDF (S3 or HTTP)
 * @param {Object} event.userRequest - Natural language request for processing
 * @param {string} [event.jobId] - Optional existing job ID for continuation
 * @param {Context} context - Lambda context
 * @returns {Object} Job information including status and output location
 */
exports.handler = async (event, context) => {
  try {
    // Create or retrieve job record
    const jobId = event.jobId || generateJobId();
    const job = await getOrCreateJob(jobId, event);
    
    // Determine next action using LLM
    const nextAction = await planNextAction(job);
    
    // Execute action if needed
    if (nextAction.type !== 'complete') {
      await executeAction(job, nextAction);
      
      // Schedule continuation for longer processing
      if (context.getRemainingTimeInMillis() < 10000) {
        await scheduleContinuation(jobId);
        return {
          jobId,
          status: 'processing',
          message: 'Processing in progress, check status endpoint'
        };
      }
      
      // If time remains, process next action immediately
      return await exports.handler({ jobId }, context);
    }
    
    // Processing complete
    return {
      jobId,
      status: 'complete',
      outputUrl: job.outputUrl,
      processingTime: calculateProcessingTime(job),
      operations: summarizeOperations(job)
    };
  } catch (error) {
    console.error('Orchestration error:', error);
    await updateJobStatus(event.jobId, 'error', error.message);
    
    return {
      jobId: event.jobId,
      status: 'error',
      error: error.message,
      suggestion: suggestRecoveryAction(error)
    };
  }
};
```

### 2. LLM Integration

```javascript
/**
 * Determines the next processing action using LLM
 * 
 * @param {Object} job - Current job state
 * @returns {Object} Next action to take
 */
async function planNextAction(job) {
  // Prepare context for LLM
  const prompt = buildActionPrompt(job);
  
  // Call LLM API (OpenAI, Azure, etc.)
  const llmResponse = await callLLM(prompt, {
    tools: PDF_TOOLS_DEFINITIONS,
    temperature: 0.2,
    max_tokens: 500
  });
  
  // Parse LLM response
  return parseLLMAction(llmResponse, job);
}

/**
 * Tool definitions for LLM function calling
 */
const PDF_TOOLS_DEFINITIONS = [
  {
    name: "resize_pdf",
    description: "Resize PDF pages by scaling or changing dimensions",
    parameters: {
      type: "object",
      properties: {
        scale: {
          type: "number",
          description: "Scale factor (e.g., 0.5 for half size)"
        },
        width: {
          type: "number",
          description: "Target width in points"
        },
        height: {
          type: "number",
          description: "Target height in points"
        },
        preserveAspectRatio: {
          type: "boolean",
          description: "Whether to preserve the aspect ratio"
        },
        pages: {
          type: "array",
          items: { type: "number" },
          description: "Specific pages to resize (empty for all)"
        }
      }
    }
  },
  // Definitions for other tools...
  {
    name: "complete_processing",
    description: "Mark processing as complete, no further actions needed",
    parameters: {
      type: "object",
      properties: {
        summary: {
          type: "string",
          description: "Summary of all processing performed"
        }
      },
      required: ["summary"]
    }
  }
];
```

### 3. Action Execution

```javascript
/**
 * Executes a PDF processing action
 * 
 * @param {Object} job - Current job state
 * @param {Object} action - Action details from LLM
 * @returns {Object} Execution result
 */
async function executeAction(job, action) {
  // Log action for audit
  await logJobAction(job.jobId, action);
  
  // Update job state
  const updatedJob = await updateJobState(job.jobId, {
    currentAction: action,
    lastUpdated: new Date().toISOString(),
    actionCount: (job.actionCount || 0) + 1
  });
  
  // Map action to Lambda function
  const functionName = mapActionToFunction(action.type);
  
  // Prepare Lambda parameters
  const params = {
    FunctionName: functionName,
    Payload: JSON.stringify({
      jobId: job.jobId,
      bucketName: job.inputBucket,
      key: job.currentKey,
      outputBucket: job.outputBucket,
      outputKey: generateOutputKey(job, action),
      parameters: action.parameters
    })
  };
  
  // Invoke Lambda
  const lambda = new AWS.Lambda();
  const result = await lambda.invoke(params).promise();
  
  // Parse result
  const payload = JSON.parse(result.Payload);
  
  // Update job with result
  if (payload.success) {
    await updateJobState(job.jobId, {
      currentKey: payload.outputKey,
      results: [...(job.results || []), {
        action: action.type,
        parameters: action.parameters,
        metadata: payload.metadata,
        timestamp: new Date().toISOString()
      }]
    });
  } else {
    throw new Error(`Action ${action.type} failed: ${payload.error}`);
  }
  
  return payload;
}
```

### 4. Job State Management

```javascript
/**
 * Creates a new processing job
 * 
 * @param {string} jobId - Unique job identifier
 * @param {Object} event - Initial request event
 * @returns {Object} Created job record
 */
async function createJob(jobId, event) {
  // Download PDF if from external URL
  const { bucket, key } = await ensurePdfInS3(event.pdfUrl);
  
  // Create job record
  const job = {
    jobId,
    status: 'initializing',
    userRequest: event.userRequest,
    inputBucket: bucket,
    originalKey: key,
    currentKey: key,
    outputBucket: process.env.OUTPUT_BUCKET,
    createdAt: new Date().toISOString(),
    lastUpdated: new Date().toISOString(),
    actionCount: 0,
    results: []
  };
  
  // Save to DynamoDB
  const params = {
    TableName: process.env.JOBS_TABLE,
    Item: job
  };
  
  const dynamoDb = new AWS.DynamoDB.DocumentClient();
  await dynamoDb.put(params).promise();
  
  return job;
}

/**
 * Retrieves a job by ID
 * 
 * @param {string} jobId - Job identifier
 * @returns {Object} Job record
 */
async function getJob(jobId) {
  const params = {
    TableName: process.env.JOBS_TABLE,
    Key: { jobId }
  };
  
  const dynamoDb = new AWS.DynamoDB.DocumentClient();
  const result = await dynamoDb.get(params).promise();
  
  if (!result.Item) {
    throw new Error(`Job ${jobId} not found`);
  }
  
  return result.Item;
}

/**
 * Updates job state
 * 
 * @param {string} jobId - Job identifier
 * @param {Object} updates - Fields to update
 * @returns {Object} Updated job
 */
async function updateJobState(jobId, updates) {
  // Build update expression
  const updateExpressions = [];
  const expressionAttributeNames = {};
  const expressionAttributeValues = {};
  
  Object.entries(updates).forEach(([key, value]) => {
    updateExpressions.push(`#${key} = :${key}`);
    expressionAttributeNames[`#${key}`] = key;
    expressionAttributeValues[`:${key}`] = value;
  });
  
  // Always update lastUpdated
  updateExpressions.push('#lastUpdated = :lastUpdated');
  expressionAttributeNames['#lastUpdated'] = 'lastUpdated';
  expressionAttributeValues[':lastUpdated'] = new Date().toISOString();
  
  const params = {
    TableName: process.env.JOBS_TABLE,
    Key: { jobId },
    UpdateExpression: `SET ${updateExpressions.join(', ')}`,
    ExpressionAttributeNames: expressionAttributeNames,
    ExpressionAttributeValues: expressionAttributeValues,
    ReturnValues: 'ALL_NEW'
  };
  
  const dynamoDb = new AWS.DynamoDB.DocumentClient();
  const result = await dynamoDb.update(params).promise();
  
  return result.Attributes;
}
```

### 5. Example LLM Prompts

#### Initial Planning Prompt

```
You are an AI PDF processing expert. Your task is to analyze the user's request and determine the best sequence of operations to process their PDF.

User request: "${job.userRequest}"
PDF information: ${pdfMetadata}

Based on the request, determine which PDF operation to perform next.

Available operations:
${formatToolDescriptions(PDF_TOOLS_DEFINITIONS)}

Return a JSON object with your chosen operation and parameters. If you believe processing is complete, use the complete_processing operation.

Your response must be valid JSON. For example:
{"operation": "resize_pdf", "parameters": {"scale": 0.5}}
```

#### Continuation Prompt

```
You are continuing to process a PDF. Review the history to determine the next step.

Original request: "${job.userRequest}"
Current PDF state: ${currentPdfMetadata}

Operations performed so far:
${formatOperationHistory(job.results)}

Based on the original request and processing history, determine which PDF operation to perform next, or indicate that processing is complete.

Available operations:
${formatToolDescriptions(PDF_TOOLS_DEFINITIONS)}

Return a JSON object with your chosen operation and parameters. If you believe processing is complete, use the complete_processing operation.
```

## Orchestrator Design Strategies

### 1. State-based vs. Reactive

The orchestrator supports two execution modes:

- **State-based**: Predetermine all processing steps upfront
  - Advantages: Faster execution, predictable
  - Best for: Simple requests with clear steps

- **Reactive**: Determine next step based on result of previous step
  - Advantages: Adaptable, handles unexpected document structure
  - Best for: Complex processing with contingent steps

### 2. Execution Patterns

Three execution patterns are supported:

1. **Direct Lambda Invocation**
   - Simple, synchronous execution
   - Lower overhead, easier to debug
   - Limited by Lambda timeout (15 min max)

2. **Step Functions State Machine**
   - Handles long-running processes
   - Visual workflow tracking
   - Better error handling and retry capabilities
   - More complex to set up

3. **Event-driven with SQS/SNS**
   - Most scalable and resilient
   - Completely decoupled components
   - Complex to debug and monitor
   - Best for high-volume production

### 3. Performance Optimization

- Use in-memory caching for repeated operations on the same document
- Implement prefix optimization for S3 to avoid hot partitions
- Consider Lambda Provisioned Concurrency for low-latency requirements
- Use S3 Transfer Acceleration for large PDFs

## DynamoDB Schema

### Jobs Table

```
TableName: ${ProjectName}-jobs-${Environment}
PrimaryKey: jobId (string)
GSI1: userIdCreatedAtIndex
  - PartitionKey: userId
  - SortKey: createdAt

Attributes:
- jobId (string): Unique job identifier
- userId (string): User who created the job
- status (string): current, complete, error
- userRequest (string): Original processing request
- inputBucket (string): S3 bucket with original file
- originalKey (string): S3 key of original file
- currentKey (string): S3 key of file in its current state
- outputBucket (string): S3 bucket for output file
- outputKey (string): S3 key of final output (when complete)
- outputUrl (string): Public URL of final output (when complete)
- createdAt (string): ISO timestamp of creation
- lastUpdated (string): ISO timestamp of last update
- actionCount (number): Number of actions performed
- results (list): History of actions and results
- errorMessage (string): Error message if status is 'error'
```

## Monitoring and Debugging

1. **Logging Strategy**
   - Consistent structured JSON logging
   - Include jobId, actionType in all logs
   - Log request/response payloads (excluding sensitive data)
   - Use log levels (DEBUG, INFO, WARN, ERROR)

2. **CloudWatch Metrics**
   - Custom metrics for each action type
   - Track latency, success rate, error types
   - Job duration, step count, LLM token usage

3. **X-Ray Tracing**
   - Trace across Lambda functions
   - Identify performance bottlenecks
   - Track S3 and DynamoDB interactions

4. **Alerting**
   - Alert on high error rates or timeouts
   - Track cost anomalies
   - Monitor LLM API failures

## Security and Compliance

1. **Input Validation**
   - Validate all user inputs
   - Scan uploaded PDFs for malware
   - Set size limits on input files

2. **Permissions**
   - Apply least privilege IAM policies
   - Scope permissions to specific S3 prefixes
   - Rotate credentials and API keys regularly

3. **Data Handling**
   - Encrypt data at rest (S3, DynamoDB)
   - Encrypt data in transit
   - Implement lifecycle policies for data retention
   - Never pass sensitive PDF content directly to LLM