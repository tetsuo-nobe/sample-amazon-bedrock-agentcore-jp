#!/bin/bash
# Deploy the AgentCore Gateway Lambda function using AWS SAM

set -e

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    echo "Activating virtual environment from parent directory..."
    source ../.venv/bin/activate
    echo "Virtual environment activated"
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Read the agent ARN from 02_runtime configuration
YAML_FILE="../02_runtime/.bedrock_agentcore.yaml"

if [ ! -f "$YAML_FILE" ]; then
    echo "Error: AgentCore configuration file not found at $YAML_FILE"
    echo "Please ensure you have deployed the AgentCore Runtime in 02_runtime first."
    exit 1
fi

# Extract agent ARN from YAML file using grep and awk
RUNTIME_ARN=$(grep "agent_arn:" $YAML_FILE | awk '{print $2}')

if [ -z "$RUNTIME_ARN" ]; then
    echo "Error: Could not find agent_arn in $YAML_FILE"
    exit 1
fi

STACK_NAME="AWS-Cost-Estimator-Agent"
REGION=${AWS_DEFAULT_REGION:-us-east-1}

echo "Deploying AgentCore Gateway Lambda..."
echo "Runtime ARN: $RUNTIME_ARN"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"

# Build the SAM application
echo "Building SAM application..."
sam build

# Deploy the SAM application
echo "Deploying SAM application..."
sam deploy \
    --stack-name $STACK_NAME \
    --region $REGION \
    --parameter-overrides "AgentCoreRuntimeArn=$RUNTIME_ARN" \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --resolve-s3

# Get the Lambda function ARN from stack outputs
LAMBDA_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='AgentCoreGatewayFunctionArn'].OutputValue" \
    --output text)

if [ -z "$LAMBDA_ARN" ]; then
    echo "Error: Could not retrieve Lambda function ARN from stack outputs"
    exit 1
fi

# Save Lambda ARN to gateway configuration for create_gateway.py
CONFIG_FILE="gateway_config.json"
echo "Saving Lambda ARN to $CONFIG_FILE..."

# Create or update the configuration file with Lambda ARN
cat > $CONFIG_FILE << EOF
{
  "lambda_arn": "$LAMBDA_ARN",
  "deployment_timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "stack_name": "$STACK_NAME",
  "region": "$REGION"
}
EOF

echo ""
echo "Deployment complete!"
echo "Lambda Function ARN: $LAMBDA_ARN"
echo "Configuration saved to: $CONFIG_FILE"
echo ""
echo "Next steps:"
echo "1. Run 'uv run python create_gateway.py' to set up the Gateway (Lambda ARN will be read from config)"
echo "2. The Gateway will automatically use the deployed Lambda function as its target"

# Deactivate virtual environment if it was activated
if [ ! -z "$VIRTUAL_ENV" ]; then
    echo "Deactivating virtual environment..."
    deactivate
fi
