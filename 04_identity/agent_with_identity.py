"""
Strands agent that uses AgentCore Identity with existing Cognito M2M OAuth.

This implementation demonstrates the integration of AgentCore Identity with
a Strands agent that calls the existing Gateway. The @requires_access_token
decorator handles OAuth M2M authentication transparently.

Key Features:
- Uses @requires_access_token for automatic token management
- Integrates with existing Gateway infrastructure
- Provides secure, authenticated access to MCP tools
- Follows two-step pattern: Get token → Create agent → Use tools

Prerequisites:
- Gateway deployed (03_gateway)
- OAuth2 credential provider created (setup_credential_provider.py)

Usage:
    from agent_with_identity import AgentWithIdentity
    agent = AgentWithIdentity()
    result = await agent.estimate_costs("architecture description")
"""

import asyncio
import json
from typing import Optional
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.identity.auth import requires_access_token
import logging
from pathlib import Path
from setup_credential_provider import PROVIDER_NAME

# Configure logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AgentWithIdentity:
    """
    Agent that uses AgentCore Identity with existing Cognito M2M authentication.
    
    This class demonstrates how to:
    1. Load existing Gateway configuration
    2. Use @requires_access_token for authentication
    3. Create authenticated MCP clients
    4. Perform secure API calls through the Gateway
    """
    
    def __init__(self):
        """Initialize agent with existing gateway configuration"""
        # Load existing gateway configuration
        config_path = Path("../03_gateway/gateway_config.json")
        if not config_path.exists():
            raise FileNotFoundError(
                f"Gateway configuration not found at {config_path}. "
                "Please deploy the gateway first using 03_gateway setup."
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.gateway_config = json.load(f)
            logger.info("✅ Loaded gateway configuration")
        except Exception as e:
            raise RuntimeError(f"Failed to load gateway configuration: {e}")
        
        # Extract configuration values
        self.gateway_url = self.gateway_config['gateway_url']
        self.cognito_config = self.gateway_config['cognito']
        self.region = self.gateway_config['region']
        
        logger.info(f"Gateway URL: {self.gateway_url}")
        logger.info(f"Cognito scope: {self.cognito_config['scope']}")
    
    async def get_access_token(self) -> str:
        """
        Get access token using AgentCore Identity.
        
        This method uses the @requires_access_token decorator to handle
        OAuth M2M authentication transparently. The decorator:
        1. Checks for cached tokens
        2. Performs OAuth client credentials flow if needed
        3. Manages token lifecycle automatically
        4. Provides the token securely to the decorated function
        
        Returns:
            str: Access token for authenticated API calls
        """
        
        # Create wrapper function with @requires_access_token decorator
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-getting-started-step3.html
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/common-use-cases.html
        @requires_access_token(
            provider_name=PROVIDER_NAME,
            scopes=[self.cognito_config['scope']],
            auth_flow="M2M",  # Machine-to-Machine authentication
            force_authentication=False  # Use cached tokens when available
        )    
        async def _get_token(*, access_token: str) -> str:
            """
            Inner function that receives the access token from AgentCore Identity.
            
            The @requires_access_token decorator injects the access_token parameter
            automatically after handling the OAuth flow.
            
            Args:
                access_token: OAuth access token (injected by decorator)
                
            Returns:
                str: The access token for use in API calls
            """
            logger.info("✅ Successfully obtained access token via AgentCore Identity")
            logger.info(f"   Token prefix: {access_token[:20]}...")
            logger.info(f"   Token length: {len(access_token)} characters")
            return access_token
        
        # Call the decorated function to get the token
        return await _get_token()
    
    async def estimate_costs(self, architecture_description: str) -> Optional[str]:
        """
        Complete flow: Get token → Create agent → Estimate costs.
        
        This demonstrates the recommended two-step pattern for AgentCore Identity:
        1. Obtain access token using @requires_access_token
        2. Use token to create authenticated clients and perform operations
        
        Args:
            architecture_description: Description of AWS architecture to estimate
            
        Returns:
            str: Cost estimation results from the agent
        """
        
        # Step 1: Get access token using AgentCore Identity
        logger.info("Step 1: Obtaining access token via AgentCore Identity...")
        access_token = await self.get_access_token()
        
        # Step 2: Create agent with authenticated MCP client
        logger.info("Step 2: Creating agent with authenticated MCP client...")
        
        def create_streamable_http_transport():
            """
            Create streamable HTTP transport with Bearer token authentication.
            
            This transport will be used by the MCP client to make authenticated
            requests to the Gateway.
            """
            return streamablehttp_client(
                self.gateway_url, 
                headers={"Authorization": f"Bearer {access_token}"}
            )
        
        def get_full_tools_list(client):
            """
            List all available tools with support for pagination.
            
            The Gateway may return tools in paginated responses, so we need
            to handle pagination to get the complete list.
            
            Args:
                client: MCP client instance
                
            Returns:
                list: Complete list of available tools
            """
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

        # Create MCP client using the authenticated transport
        mcp_client = MCPClient(create_streamable_http_transport)

        result = None
        try:
            with mcp_client:
                # Step 3: List available tools through authenticated connection
                logger.info("Step 3: Listing tools via authenticated MCP client...")
                tools = get_full_tools_list(mcp_client)
                tool_names = [tool.tool_name for tool in tools]
                logger.info(f"Available tools: {tool_names}")
                
                if not tools:
                    raise RuntimeError("No tools available from Gateway")
                
                # Step 4: Create agent with the authenticated tools
                logger.info("Step 4: Creating Strands agent with authenticated tools...")
                agent = Agent(
                    tools=tools,
                    system_prompt="""You are an AWS cost estimation assistant.
                    You help automated systems and services estimate costs for AWS architectures.
                    """
                )
                
                # Step 5: Use the agent to estimate costs
                logger.info("Step 5: Running cost estimation with authenticated agent...")
                prompt = (
                    f"Please use the aws_cost_estimation tool to estimate costs for this architecture: "
                    f"{architecture_description}"
                )
            
                result = agent(prompt)
                logger.info("✅ Cost estimation completed successfully")
                
        except Exception as e:
            logger.error(f"Error during cost estimation: {e}")
            return None  # Return None to indicate failure
        
        return result
