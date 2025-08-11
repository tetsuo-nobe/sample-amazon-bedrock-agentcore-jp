"""
Create AgentCore Gateway with Lambda target using AgentCore SDK

This script automatically retrieves the Lambda ARN from configuration or CloudFormation,
handles OIDC DNS propagation delays, and provides robust resource cleanup.

Usage:
  uv run python create_gateway.py                    # Auto-detect Lambda ARN
  uv run python create_gateway.py --lambda-arn ARN   # Specify Lambda ARN explicitly
  uv run python create_gateway.py --force            # Force recreation of resources
"""

import json
import logging
import argparse
import boto3
import time
import requests
from pathlib import Path
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CONFIG_FILE = Path('gateway_config.json')


def main():
    """Main function to create Gateway with Lambda target"""
    parser = argparse.ArgumentParser(description='Create AgentCore Gateway with Lambda target')
    parser.add_argument('--lambda-arn', help='Lambda function ARN (auto-detected if not provided)')
    parser.add_argument('--force', action='store_true', help='Force recreation of resources')
    args = parser.parse_args()

    try:
        logger.info("Starting AgentCore Gateway setup...")
        
        # Get Lambda ARN
        lambda_arn = args.lambda_arn or load_lambda_arn()
        logger.info(f"Using Lambda ARN: {lambda_arn}")

        # Initialize Gateway client
        client = GatewayClient(region_name=boto3.Session().region_name)
        
        # Handle existing configuration
        existing_config = load_config() if CONFIG_FILE.exists() else None
        
        # Determine what needs to be created based on existing config
        has_cognito = existing_config and 'cognito' in existing_config
        has_gateway = existing_config and 'gateway_id' in existing_config
        has_target = existing_config and 'target_id' in existing_config
        
        # If everything is complete and not forcing, show summary and exit
        if existing_config and has_cognito and has_gateway and has_target and not args.force:
            logger.info("All components already configured (use --force to recreate)")
            print_config_summary(existing_config)
            return
        
        # Show what we're going to do
        if existing_config and not args.force:
            logger.info("Found partial configuration, completing setup...")
            if has_cognito:
                logger.info("  ✅ Cognito already configured")
            if has_gateway:
                logger.info("  ✅ Gateway already configured")
            if has_target:
                logger.info("  ✅ Target already configured")
        
        if args.force:
            logger.info("Force flag set - will recreate all resources")
            if existing_config:
                logger.info("Cleaning up existing resources...")
                cleanup_resources(client, existing_config)
            has_cognito = has_gateway = has_target = False
        
        # Step 1: Handle Cognito OAuth authorizer
        if has_cognito:
            logger.info("✅ Reusing existing Cognito configuration")
            cognito_config = existing_config['cognito']
            # Reconstruct cognito_result for compatibility with later code
            cognito_result = {
                'client_info': cognito_config,
                'authorizer_config': {
                    # We'll need this for gateway creation if gateway doesn't exist
                    'type': 'JWT',
                    'userPoolId': cognito_config['user_pool_id']
                }
            }
        else:
            logger.info("Creating Cognito OAuth authorizer...")
            cognito_result = client.create_oauth_authorizer_with_cognito("AWSCostEstimationResourceServer")
            
            cognito_config = {
                "cognito": {
                    "client_id": cognito_result['client_info']['client_id'],
                    "client_secret": cognito_result['client_info']['client_secret'],
                    "token_endpoint": cognito_result['client_info']['token_endpoint'],
                    "scope": cognito_result['client_info']['scope'],
                    "user_pool_id": cognito_result['client_info']['user_pool_id']
                }
            }
            save_config(cognito_config)
            logger.info("✅ Cognito configuration saved")

        # Step 2: Handle Gateway creation
        if has_gateway:
            logger.info("✅ Reusing existing Gateway")
            gateway_id = existing_config['gateway_id']
            gateway_url = existing_config['gateway_url']
            # Create gateway object for target creation
            gateway = {"gatewayId": gateway_id, "gatewayUrl": gateway_url}
        else:
            logger.info("Creating MCP Gateway...")
            gateway = client.create_mcp_gateway(
                name="AWSCostEstimationGateway",
                role_arn=None,
                authorizer_config=cognito_result["authorizer_config"],
                enable_semantic_search=False
            )
            
            gateway_id = gateway["gatewayId"]
            gateway_url = gateway["gatewayUrl"]
            logger.info(f"Gateway created: {gateway_id}")
            
            # Save gateway configuration immediately after creation
            save_config({
                "gateway_id": gateway_id,
                "gateway_url": gateway_url
            })
            logger.info("✅ Gateway configuration saved")
        
        # Wait for OIDC endpoint availability
        logger.info("Waiting for OIDC endpoint to become available...")
        oidc_url = get_oidc_discovery_url(cognito_result)
        
        if not wait_for_oidc_endpoint(oidc_url):
            logger.warning("OIDC endpoint may not be ready, but proceeding...")
        
        # Step 3: Handle Lambda target creation
        if has_target:
            logger.info("✅ Reusing existing Lambda target")
            target_id = existing_config['target_id']
        else:
            logger.info("Adding Lambda target to Gateway...")
            tool_schema = [
                {
                    "name": "aws_cost_estimation",
                    "description": "Estimate AWS costs for a given architecture description",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "architecture_description": {
                                "type": "string",
                                "description": "Description of the AWS architecture to estimate costs for"
                            }
                        },
                        "required": ["architecture_description"]
                    }
                }
            ]

            # Create lambda target with required credentialProviderConfigurations
            # Note: toolkit's create_mcp_gateway_target doesn't handle custom target_payload + credentials
            # Reference: https://github.com/aws/bedrock-agentcore-starter-toolkit/pull/57 
            target_name = "AWSCostEstimationLambdaTarget"
            
            create_request = {
                "gatewayIdentifier": gateway["gatewayId"],
                "name": target_name,
                "targetConfiguration": {
                    "mcp": {
                        "lambda": {
                            "lambdaArn": lambda_arn,
                            "toolSchema": {
                                "inlinePayload": tool_schema
                            }
                        }
                    }
                },
                "credentialProviderConfigurations": [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]
            }
            
            logger.info("Creating Lambda target with custom schema and credentials...")
            logger.info(f"Request: {create_request}")
            
            # Use boto3 client directly since toolkit method doesn't support this combination
            bedrock_client = client.session.client('bedrock-agentcore-control')
            target_response = bedrock_client.create_gateway_target(**create_request)
            
            target_id = target_response["targetId"]
            logger.info(f"✓ Lambda target created: {target_id}")
            
            # Wait for target to be ready with 5-minute timeout
            max_wait = 300  # 5 minutes
            interval = 5    # 5 seconds
            start_time = time.time()
            attempt = 1
            
            logger.info("⏳ Waiting for target to be ready...")
            logger.info(f"⏳ Timeout: {max_wait}s, Check interval: {interval}s")
            
            while time.time() - start_time < max_wait:
                target_status = bedrock_client.get_gateway_target(
                    gatewayIdentifier=gateway["gatewayId"],
                    targetId=target_id
                )
                logger.info(f"⏳ Attempt {attempt}: Status {target_status['status']}")
                
                if target_status["status"] == "READY":
                    elapsed = time.time() - start_time
                    logger.info(f"✅ Target is ready after {elapsed:.1f}s")
                    break
                elif target_status["status"] == "FAILED":
                    raise Exception(f"Target creation failed: {target_status}")
                
                remaining = max_wait - (time.time() - start_time)
                if remaining > interval:
                    logger.info(f"⏳ Waiting {interval}s... ({remaining:.0f}s remaining)")
                    time.sleep(interval)
                    attempt += 1
                else:
                    break
            else:
                raise Exception(f"Target failed to become ready within {max_wait}s")
            
            logger.info(f"Lambda target created: {target_id}")
            
            # Save target configuration immediately
            save_config({
                "target_id": target_id
            })
            logger.info("✅ Target configuration saved")
        
        logger.info("✅ Gateway setup complete!")
        logger.info("Next step: Run 'uv run python test_gateway.py' to test the Gateway")
        
    except Exception as e:
        logger.error(f"Gateway setup failed: {e}")
        return  # Handle error without re-raising


def load_lambda_arn():
    """Load Lambda ARN from config file or CloudFormation stack"""
    # Try config file first
    if CONFIG_FILE.exists():
        try:
            config = load_config()
            if config.get('lambda_arn'):
                return config['lambda_arn']
        except Exception as e:
            logger.debug(f"Config file read failed: {e}")
    
    # Fallback to CloudFormation
    logger.info("Checking CloudFormation for Lambda ARN...")
    try:
        cf_client = boto3.client('cloudformation')
        stack_name = "AWS-Cost-Estimator-Agent"
        
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        
        for output in outputs:
            if output['OutputKey'] == 'AgentCoreGatewayFunctionArn':
                lambda_arn = output['OutputValue']
                
                # Save to config for future use
                save_config({
                    "lambda_arn": lambda_arn,
                    "stack_name": stack_name,
                    "source": "cloudformation"
                })
                
                return lambda_arn
        
        raise ValueError("Lambda ARN not found in CloudFormation outputs")
        
    except Exception as e:
        raise ValueError(
            f"Could not retrieve Lambda ARN: {e}\n"
            "Please run './deploy.sh' first to deploy the Lambda function"
        )


def wait_for_oidc_endpoint(oidc_url, max_wait=600, interval=30):
    """Wait for OIDC discovery endpoint to become available
    
    Based on real-world testing, OIDC endpoints can take 5+ minutes to become available
    due to DNS propagation and service initialization delays.
    """
    start_time = time.time()
    attempt = 1
    
    logger.info(f"⏳ Waiting for OIDC endpoint: {oidc_url}")
    logger.info(f"⏳ Timeout: {max_wait}s, Check interval: {interval}s")
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(oidc_url, timeout=10)
            logger.info(f"⏳ Attempt {attempt}: HTTP {response.status_code}")
            
            # Raise exception for HTTP error status codes (4xx, 5xx)
            response.raise_for_status()
            
            if response.status_code == 200:
                elapsed = time.time() - start_time
                logger.info(f"✅ OIDC endpoint available after {elapsed:.1f}s")
                # Verify it's actually valid JSON
                try:
                    json_data = response.json()
                    if 'issuer' in json_data:
                        logger.info("✅ OIDC discovery document is valid")
                        return True
                    else:
                        logger.warning("⚠️ OIDC response missing 'issuer' field")
                except ValueError:
                    logger.warning("⚠️ OIDC response is not valid JSON")
            elif response.status_code == 404:
                logger.info("⏳ OIDC endpoint not found yet (404)")
            elif response.status_code >= 500:
                logger.info(f"⏳ Server error ({response.status_code}), service may be initializing")
            else:
                logger.info(f"⏳ Unexpected status code: {response.status_code}")
                
        except requests.exceptions.HTTPError as e:
            logger.info(f"⏳ Attempt {attempt}: HTTP error {e.response.status_code} - {e}")
        except requests.exceptions.Timeout:
            logger.info(f"⏳ Attempt {attempt}: Request timeout")
        except requests.exceptions.ConnectionError:
            logger.info(f"⏳ Attempt {attempt}: Connection error (DNS/network)")
        except requests.exceptions.RequestException as e:
            logger.info(f"⏳ Attempt {attempt}: Request error - {type(e).__name__}")
        
        remaining = max_wait - (time.time() - start_time)
        if remaining > interval:
            logger.info(f"⏳ Waiting {interval}s... ({remaining:.0f}s remaining)")
            time.sleep(interval)
            attempt += 1
        else:
            break
    
    logger.warning(f"❌ OIDC endpoint not available after {max_wait}s")
    return False


def get_oidc_discovery_url(cognito_result):
    """Extract OIDC discovery URL from Cognito configuration"""
    user_pool_id = cognito_result['client_info']['user_pool_id']
    region = boto3.Session().region_name
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"


def cleanup_resources(client, config):
    """Clean up existing Gateway resources"""
    try:
        # Delete target first
        if 'target_id' in config and 'gateway_id' in config:
            client.delete_mcp_gateway_target(config['gateway_id'], config['target_id'])
            logger.info("Deleted Gateway target")
        
        # Delete Gateway
        if 'gateway_id' in config:
            client.delete_mcp_gateway(config['gateway_id'])
            logger.info("Deleted Gateway")
        
        # Clean up Cognito resources
        cleanup_cognito_resources(config.get('cognito', {}))
        
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
    
    # Remove old config
    try:
        CONFIG_FILE.unlink()
    except OSError:
        pass


def cleanup_cognito_resources(cognito_config):
    """Clean up Cognito resources explicitly"""
    if not cognito_config.get('user_pool_id'):
        return
    
    try:
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = cognito_config['user_pool_id']
        
        # Delete app client
        if cognito_config.get('client_id'):
            cognito_client.delete_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=cognito_config['client_id']
            )
        
        # Delete resource server
        cognito_client.delete_resource_server(
            UserPoolId=user_pool_id,
            Identifier='AWSCostEstimationResourceServer'
        )
        
        # Delete user pool
        cognito_client.delete_user_pool(UserPoolId=user_pool_id)
        logger.info("Cleaned up Cognito resources")
        
    except Exception as e:
        logger.warning(f"Cognito cleanup error: {e}")


def load_config():
    """Load configuration from file"""
    with CONFIG_FILE.open('r') as f:
        return json.load(f)


def save_config(updates):
    """Update configuration file with new data"""
    config = {}
    if CONFIG_FILE.exists():
        try:
            config = load_config()
        except Exception:
            pass
    
    config.update(updates)
    
    with CONFIG_FILE.open('w') as f:
        json.dump(config, f, indent=2)


def print_config_summary(config):
    """Print a clean summary of the configuration"""
    print("\n" + "="*50)
    print("Gateway Configuration Summary")
    print("="*50)
    print(f"Gateway URL: {config.get('gateway_url', 'N/A')}")
    print(f"Gateway ID: {config.get('gateway_id', 'N/A')}")
    print(f"Client ID: {config.get('cognito', {}).get('client_id', 'N/A')}")
    print(f"Configuration: {CONFIG_FILE}")
    print("="*50)


if __name__ == "__main__":
    main()
