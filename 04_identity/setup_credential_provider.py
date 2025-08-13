"""
既存のCognito設定を使用してAgentCore Identity用のOAuth2認証プロバイダーをセットアップ。

このスクリプトは、gateway設定からの既存の
Cognito M2M OAuthセットアップと統合するOAuth2認証プロバイダーを作成します。プロバイダーは
AgentCore Identityが認証されたAPI呼び出しのためにアクセストークンをセキュアに管理できるようにします。

前提条件:
- Gatewayがデプロイ済み (03_gateway)
- bedrock-agentcore-control権限でAWS認証情報が設定済み

使用方法:
    uv run 05_identity/setup_credential_provider.py
"""

import json
import boto3
import logging
from pathlib import Path
from botocore.exceptions import ClientError

# 明確なデバッグのためのログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROVIDER_NAME = "agentcore-identity-for-gateway"

def setup_oauth2_credential_provider(provider_name: str = PROVIDER_NAME):
    """
    AgentCore Identity用のOAuth2認証プロバイダーをセットアップ。
    
    この関数は:
    1. gatewayセットアップから既存のCognito設定を読み込み
    2. CognitoディスカバリーURLを使用してOAuth2認証プロバイダーを作成
    3. M2M認証用のクライアント認証情報を設定
    
    Args:
        provider_name: 認証プロバイダーの名前
        
    Returns:
        bool: 成功した場合True、そうでなければFalse
    """
    
    # 既存のセットアップからgateway設定を読み込み
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
    
    # Cognito設定を抽出
    cognito_config = gateway_config['cognito']
    region = gateway_config['region']
    user_pool_id = cognito_config['user_pool_id']
    
    # Cognito用のOpenID ConnectディスカバリーURLを構築
    # このURLはOAuth2エンドポイントと設定を提供
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
    
    logger.info(f"Using Cognito discovery URL: {discovery_url}")
    logger.info(f"Client ID: {cognito_config['client_id']}")
    logger.info(f"Scope: {cognito_config['scope']}")
    
    # 認証プロバイダー管理用のbedrock-agentcore-controlクライアントを作成
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        logger.info(f"✅ Created AgentCore control client for region {region}")
    except Exception as e:
        logger.error(f"Failed to create AgentCore control client: {e}")
        return False
    
    # 認証プロバイダーが既に存在するかチェック
    try:
        logger.info("Checking for existing credential providers...")
        # APIリファレンス: https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_ListOauth2CredentialProviders.html
        response = client.list_oauth2_credential_providers()
        
        # レスポンスには'credentialProviders'配列が含まれる
        for provider in response.get('credentialProviders', []):
            if provider['name'] == provider_name:
                logger.info(f"✅ Credential provider '{provider_name}' already exists")
                logger.info(f"   ARN: {provider['credentialProviderArn']}")
                logger.info(f"   Created: {provider['createdTime']}")
                return True
                
    except ClientError as e:
        logger.error(f"Failed to list credential providers: {e}")
        return False
    
    # 新しい認証プロバイダー設定を作成
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
        # APIリファレンス: https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateOauth2CredentialProvider.html
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
    """認証プロバイダーをセットアップするメイン関数"""
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
