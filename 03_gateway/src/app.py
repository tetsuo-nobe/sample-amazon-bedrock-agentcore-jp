"""
Simple Lambda function for AgentCore Gateway that provides aws_cost_estimation tool

This Lambda function calls the AgentCore Runtime deployed in 02_runtime
to estimate AWS costs using the cost estimator agent.
"""

import json
import logging
import os
import boto3
import uuid

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


def lambda_handler(event, context):
    """
    Handle aws_cost_estimation tool invocation from Gateway
    
    Args:
        event: Contains the architecture description to estimate costs for
        context: Lambda context with Gateway metadata. Its `client_context` should contain
        ClientContext(custom={
            'bedrockAgentCoreGatewayId': 'Y02ERAYBHB'
            'bedrockAgentCoreTargetId': 'RQHDN3J002'
            'bedrockAgentCoreMessageVersion': '1.0'
            'bedrockAgentCoreToolName': 'weather_tool'
            'bedrockAgentCoreSessionId': ''
        },env=None,client=None]
        please refer : https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/02-AgentCore-gateway/01-transform-lambda-into-mcp-tools

    Returns:
        Cost estimation result from AgentCore Runtime
    """
    try:
        # Log the incoming request
        logger.info(f"Received event: {json.dumps(event)}")
        logger.info(f"Context: {context.client_context}")
        
        # Extract tool name from context
        tool_name = context.client_context.custom.get('bedrockAgentCoreToolName', '')
        
        # Remove any prefix added by Gateway (format: targetName___toolName)
        if "___" in tool_name:
            tool_name = tool_name.split("___")[-1]
        
        logger.info(f"Processing tool: {tool_name}")
        
        # Verify this is the aws_cost_estimation tool
        if tool_name != 'aws_cost_estimation':
            return {
                'statusCode': 400,
                'body': f"Unknown tool: {tool_name}"
            }
        
        # Get the architecture description from event
        architecture_description = event.get('architecture_description', '')
        if not architecture_description:
            return {
                'statusCode': 400,
                'body': "Missing required parameter: architecture_description"
            }

        # Get AgentCore Runtime ARN from environment
        runtime_arn = os.environ.get('AGENTCORE_RUNTIME_ARN')
        if not runtime_arn:
            raise ValueError("AGENTCORE_RUNTIME_ARN environment variable not set")
        
        # Call the AgentCore Runtime
        result = invoke_cost_estimator_runtime(runtime_arn, architecture_description)

        return {
            'statusCode': 200,
            'body': result
        }
        
    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }


def invoke_cost_estimator_runtime(runtime_arn, architecture_description):
    """
    Invoke the cost estimator agent in AgentCore Runtime
    
    Args:
        runtime_arn: ARN of the AgentCore Runtime
        architecture_description: Description of AWS architecture to estimate
        
    Returns:
        Cost estimation result as string
    """
    # Initialize AgentCore client
    client = boto3.client('bedrock-agentcore')
    
    # Prepare the payload for cost estimation
    payload = {
        "prompt": architecture_description
    }
    
    # Generate session ID for this request
    session_id = str(uuid.uuid4())
    
    logger.info(f"Invoking AgentCore Runtime with session: {session_id}")
    
    # Invoke the runtime
    # Explicitly set the traceId to avoid `Value at 'traceId' failed to satisfy constraint: Member must have length less than or equal to 128\` error
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode('utf-8'),
        traceId=session_id,
    )
    
    # Process response
    if "text/event-stream" in response.get("contentType", ""):    
        # Handle streaming response
        content = []
        for line in response["response"].iter_lines(chunk_size=10):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                    content.append(line)

    elif response.get("contentType") == "application/json":
        # Handle standard JSON response
        content = []
        for chunk in response.get("response", []):
            content.append(chunk.decode('utf-8'))
    
    else:
        content = response.get("response", [])
    
    result = ''.join(content)
    return result
