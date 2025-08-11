"""
Test the AgentCore Gateway by invoking the aws_cost_estimation tool

This script demonstrates how to:
1. Obtain an OAuth token from Cognito
2. Call the Gateway's MCP endpoint
3. Invoke the aws_cost_estimation tool
"""

import json
import logging
import argparse
import requests
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# Configure logging with more verbose output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_oauth_token(config):
    """Get OAuth token from Cognito using bedrock_agentcore_starter_toolkit"""
    logger.info("Getting OAuth token from Cognito...")
    
    # Create GatewayClient and use its method to get access token
    gateway_client = GatewayClient()
    
    # Prepare client_info in the format expected by the method
    client_info = {
        'client_id': config['cognito']['client_id'],
        'client_secret': config['cognito']['client_secret'],
        'scope': config['cognito']['scope'],
        'token_endpoint': config['cognito']['token_endpoint']
    }
    
    token = gateway_client.get_access_token_for_cognito(client_info)
    
    logger.info("Successfully obtained OAuth token")
    return token


def test_with_mcp_client(gateway_url, token, architecture_description):
    """Test the Gateway using MCP client via Strands Agents"""
    logger.info("Testing Gateway with MCP client (Strands Agents)...")
    
    def create_streamable_http_transport():
        """Create streamable HTTP transport with authentication"""
        return streamablehttp_client(
            gateway_url, 
            headers={"Authorization": f"Bearer {token}"}
        )
    
    def get_full_tools_list(client):
        """List tools with support for pagination"""
        more_tools = True
        tools = []
        pagination_token = None
        while more_tools:
            tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
            tools.extend(tmp_tools)
            if tmp_tools.pagination_token is None:
                more_tools = False
            else:
                more_tools = True 
                pagination_token = tmp_tools.pagination_token
        return tools
    
    # Create MCP client using the pattern from AWS documentation
    mcp_client = MCPClient(create_streamable_http_transport)
    
    try:
        with mcp_client:
            # List available tools
            logger.info("Listing tools via MCP client...")
            tools = get_full_tools_list(mcp_client)
            tool_names = [tool.tool_name for tool in tools]
            logger.info(f"Found the following tools: {tool_names}")
            
            # Find the cost estimation tool
            cost_estimation_tool = None
            for tool in tools:
                if 'aws_cost_estimation' in tool.tool_name:
                    cost_estimation_tool = tool
                    break
            
            if not cost_estimation_tool:
                logger.error("No aws_cost_estimation tool found in available tools")
                return
            
            logger.info(f"Found cost estimation tool: {cost_estimation_tool.tool_name}")
            
            # Create agent with the tools
            logger.info("Creating agent with MCP tools...")
            agent = Agent(
                tools=tools,
                system_prompt="You are a helpful assistant that can estimate AWS costs. Please answer in customer's language."
            )
            
            # Test by asking the agent to use the aws_cost_estimation tool
            logger.info("\nAsking agent to estimate AWS costs...")
            
            prompt = f"Please use the aws_cost_estimation tool to estimate costs for this architecture: {architecture_description}"
            
            result = agent(prompt)
            
            logger.info("\nAgent response:")
            logger.info(result)
            
            return result
            
    except Exception as e:
        logger.error(f"MCP client test failed: {e}")


def test_with_direct_api(gateway_url, token, architecture_description):
    """Test the Gateway using direct MCP API calls"""
    logger.info("Testing Gateway with direct API calls...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    # List tools
    logger.info("Listing tools via API...")
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = requests.post(gateway_url, json=list_tools_request, headers=headers, timeout=30)
    response.raise_for_status()  # Raise exception for HTTP error codes
    
    tools_response = response.json()
    logger.info(f"Tools response: {json.dumps(tools_response, indent=2)}")
        
    # Extract tool names and find the cost estimation tool
    if 'result' in tools_response and 'tools' in tools_response['result']:
        tools = tools_response['result']['tools']
        cost_estimation_tool = None
        
        # Find the cost estimation tool (look for tool name containing 'aws_cost_estimation')
        for tool in tools:
            if 'aws_cost_estimation' in tool['name']:
                cost_estimation_tool = tool['name']
                break
        
        if not cost_estimation_tool:
            logger.error("No aws_cost_estimation tool found in available tools")
            return
            
        logger.info(f"Found cost estimation tool: {cost_estimation_tool}")
    else:
        logger.error("Unexpected tools response format")
        return
    
    # Call the tool using the dynamically acquired name
    logger.info(f"\nCalling {cost_estimation_tool} tool via API...")
    call_tool_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": cost_estimation_tool,
            "arguments": {
                "architecture_description": architecture_description
            }
        }
    }
    
    response = requests.post(gateway_url, json=call_tool_request, headers=headers, timeout=30)
    response.raise_for_status()  # Raise exception for HTTP error codes
    
    tool_response = response.json()
    logger.info(f"Tool response: {json.dumps(tool_response, indent=2)}")


def main():
    """Main test function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test AgentCore Gateway with different methods')
    parser.add_argument(
        '--tests', 
        choices=['api', 'mcp'], 
        default='api',
        help='Type of test to run: api (direct API calls) or mcp (MCP client via Strands). Default: api'
    )
    parser.add_argument(
        '--architecture',
        type=str,
        default="A simple web application with an Application Load Balancer, 2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1.",
        help='Architecture description for cost estimation. Default: A simple web application with ALB, 2 EC2 instances, and RDS MySQL'
    )
    args = parser.parse_args()
    
    try:
        # Load configuration
        with open('gateway_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        gateway_url = config['gateway_url']
        logger.info(f"Gateway URL: {gateway_url}")
        logger.info(f"Architecture: {args.architecture}")
        
        # Get OAuth token using the simplified method
        token = get_oauth_token(config)
        
        # Run test based on command line argument
        if args.tests == 'api':
            logger.info("\n" + "="*60)
            logger.info("Test: Direct API calls")
            logger.info("="*60)
            test_with_direct_api(gateway_url, token, args.architecture)
        
        elif args.tests == 'mcp':
            logger.info("\n" + "="*60)
            logger.info("Test: MCP Client (Strands Agents)")
            logger.info("="*60)
            test_with_mcp_client(gateway_url, token, args.architecture)
        
    except FileNotFoundError:
        logger.error("gateway_config.json not found. Please run python create_gateway.py first.")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    main()