"""
Setup OAuth2 credential provider for AgentCore Identity using existing Cognito configuration.

This script creates an OAuth2 credential provider that integrates with the existing
Cognito M2M OAuth setup from the gateway configuration. The provider enables
AgentCore Identity to securely manage access tokens for authenticated API calls.

Prerequisites:
- Gateway must be deployed (03_gateway)
- AWS credentials configured with bedrock-agentcore-control permissions

Usage:
    uv run 05_identity/setup_credential_provider.py
"""

import json
import boto3
import logging
from pathlib import Path
from botocore.exceptions import ClientError

# Configure logging for clear debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROVIDER_NAME = "agentcore-identity-for-gateway"

def setup_oauth2_credential_provider(provider_name: str = PROVIDER_NAME):
    """
    Setup OAuth2 credential provider for AgentCore Identity.
    
    This function:
    1. Loads existing Cognito configuration from gateway setup
    2. Creates OAuth2 credential provider using Cognito discovery URL
    3. Configures client credentials for M2M authentication
    
    Args:
        provider_name: Name for the credential provider
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Load gateway configuration from existing setup
    config_path = Path("../03_gateway/gateway_config.json")
    if not config_path.exists():
        logger.error(f"Gateway configuration not found at {config_path}")
        logger.error("Please deploy the gateway first using 03_gateway setup")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            gateway_config = json.load(f)
        logger.info("✅ Loaded existing gateway configuration")
    except Exception as e:
        logger.error(f"Failed to load gateway configuration: {e}")
        return False
    
    # Extract Cognito configuration
    cognito_config = gateway_config['cognito']
    region = gateway_config['region']
    user_pool_id = cognito_config['user_pool_id']
    
    # Construct OpenID Connect discovery URL for Cognito
    # This URL provides OAuth2 endpoints and configuration
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
    
    logger.info(f"Using Cognito discovery URL: {discovery_url}")
    logger.info(f"Client ID: {cognito_config['client_id']}")
    logger.info(f"Scope: {cognito_config['scope']}")
    
    # Create bedrock-agentcore-control client for managing credential providers
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        logger.info(f"✅ Created AgentCore control client for region {region}")
    except Exception as e:
        logger.error(f"Failed to create AgentCore control client: {e}")
        return False
    
    # Check if credential provider already exists
    try:
        logger.info("Checking for existing credential providers...")
        # API Reference: https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_ListOauth2CredentialProviders.html
        response = client.list_oauth2_credential_providers()
        
        # Response contains 'credentialProviders' array
        for provider in response.get('credentialProviders', []):
            if provider['name'] == provider_name:
                logger.info(f"✅ Credential provider '{provider_name}' already exists")
                logger.info(f"   ARN: {provider['credentialProviderArn']}")
                logger.info(f"   Created: {provider['createdTime']}")
                return True
                
    except ClientError as e:
        logger.error(f"Failed to list credential providers: {e}")
        return False
    
    # Create new credential provider configuration
    # https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CustomOauth2ProviderConfigInput.html
    # https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_Oauth2Discovery.html
    oauth2_config = {
        'customOauth2ProviderConfig': {
            'clientId': cognito_config['client_id'],
            'clientSecret': cognito_config['client_secret'],
            'oauthDiscovery': {
                'discoveryUrl': discovery_url
            }
        }
    }
    
    try:
        logger.info(f"Creating OAuth2 credential provider '{provider_name}'...")
        # API Reference: https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateOauth2CredentialProvider.html
        response = client.create_oauth2_credential_provider(
            name=provider_name,
            credentialProviderVendor='CustomOauth2',
            oauth2ProviderConfigInput=oauth2_config
        )
        
        logger.info("✅ Successfully created OAuth2 credential provider!")
        logger.info(f"   ARN: {response['credentialProviderArn']}")
        logger.info(f"   Name: {provider_name}")
        logger.info(f"   Scope to use: ['{cognito_config['scope']}']")
        logger.info("   Auth Flow: M2M (Machine-to-Machine)")
        
        return True
        
    except ClientError as e:
        logger.error(f"Failed to create credential provider: {e}")
        logger.error("Common issues:")
        logger.error("- Check AWS permissions for bedrock-agentcore-control")
        logger.error("- Verify Cognito client credentials are valid")
        logger.error("- Ensure discovery URL is accessible")
        return False

def main():
    """Main function to setup credential provider"""
    print("🚀 Setting up AgentCore Identity OAuth2 Credential Provider")
    print("=" * 60)
    
    success = setup_oauth2_credential_provider()
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("Next steps:")
        print("1. Run the identity agent test: uv run 05_identity/test_identity_agent.py")
        print("2. The agent will use @requires_access_token for authentication")
    else:
        print("\n❌ Setup failed. Please check the logs above.")

if __name__ == "__main__":
    main()
