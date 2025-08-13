"""
既存のCognito M2M OAuthでAgentCore Identityを使用するStrandsエージェント。

この実装は、既存のGatewayを呼び出すStrandsエージェントと
AgentCore Identityの統合を示します。@requires_access_token
デコレーターOAuth M2M認証を透明に処理します。

主要機能:
- 自動トークン管理のための@requires_access_tokenを使用
- 既存のGatewayインフラとの統合
- MCPツールへのセキュアで認証されたアクセスを提供
- 2ステップパターンに従う: トークン取得 → エージェント作成 → ツール使用

前提条件:
- Gatewayがデプロイ済み (03_gateway)
- OAuth2認証プロバイダーが作成済み (setup_credential_provider.py)

使用方法:
    from agent_with_identity import AgentWithIdentity
    agent = AgentWithIdentity()
    result = await agent.estimate_costs("アーキテクチャ説明")
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

# デバッグと監視のためのログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AgentWithIdentity:
    """
    既存のCognito M2M認証でAgentCore Identityを使用するエージェント。
    
    このクラスは以下の方法を示します:
    1. 既存のGateway設定を読み込み
    2. 認証のための@requires_access_tokenを使用
    3. 認証されたMCPクライアントを作成
    4. Gatewayを通じてセキュアなAPI呼び出しを実行
    """
    
    def __init__(self):
        """既存のgateway設定でエージェントを初期化"""
        # 既存のgateway設定を読み込み
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
        
        # 設定値を抽出
        self.gateway_url = self.gateway_config['gateway_url']
        self.cognito_config = self.gateway_config['cognito']
        self.region = self.gateway_config['region']
        
        logger.info(f"Gateway URL: {self.gateway_url}")
        logger.info(f"Cognito scope: {self.cognito_config['scope']}")
    
    async def get_access_token(self) -> str:
        """
        AgentCore Identityを使用してアクセストークンを取得。
        
        このメソッドは@requires_access_tokenデコレーターを使用して
        OAuth M2M認証を透明に処理します。デコレーターは:
        1. キャッシュされたトークンをチェック
        2. 必要に応じてOAuthクライアント認証フローを実行
        3. トークンのライフサイクルを自動管理
        4. デコレートされた関数にセキュアにトークンを提供
        
        Returns:
            str: 認証されたAPI呼び出し用のアクセストークン
        """
        
        # @requires_access_tokenデコレーターでラッパー関数を作成
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-getting-started-step3.html
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/common-use-cases.html
        @requires_access_token(
            provider_name=PROVIDER_NAME,
            scopes=[self.cognito_config['scope']],
            auth_flow="M2M",  # Machine-to-Machine認証
            force_authentication=False  # 利用可能な場合はキャッシュされたトークンを使用
        )    
        async def _get_token(*, access_token: str) -> str:
            """
            AgentCore Identityからアクセストークンを受け取る内部関数。
            
            @requires_access_tokenデコレーターはOAuthフローを処理した後、
            access_tokenパラメーターを自動的に注入します。
            
            Args:
                access_token: OAuthアクセストークン（デコレーターによる注入）
                
            Returns:
                str: API呼び出しで使用するアクセストークン
            """
            logger.info("✅ Successfully obtained access token via AgentCore Identity")
            logger.info(f"   Token prefix: {access_token[:20]}...")
            logger.info(f"   Token length: {len(access_token)} characters")
            return access_token
        
        # デコレートされた関数を呼び出してトークンを取得
        return await _get_token()
    
    async def estimate_costs(self, architecture_description: str) -> Optional[str]:
        """
        完全なフロー: トークン取得 → エージェント作成 → コスト見積もり。
        
        これはAgentCore Identityの推奨さ2ステップパターンを示します:
        1. @requires_access_tokenを使用してアクセストークンを取得
        2. トークンを使用して認証されたクライアントを作成し、操作を実行
        
        Args:
            architecture_description: 見積もり対象のAWSアーキテクチャの説明
            
        Returns:
            str: エージェントからのコスト見積もり結果
        """
        
        # ステップ1: AgentCore Identityを使用してアクセストークンを取得
        logger.info("Step 1: Obtaining access token via AgentCore Identity...")
        access_token = await self.get_access_token()
        
        # ステップ2: 認証されたMCPクライアントでエージェントを作成
        logger.info("Step 2: Creating agent with authenticated MCP client...")
        
        def create_streamable_http_transport():
            """
            Bearerトークン認証でストリーム可能HTTPトランスポートを作成。
            
            このトランスポートはMCPクライアントが認証された
            Gatewayへのリクエストを行うために使用されます。
            """
            return streamablehttp_client(
                self.gateway_url, 
                headers={"Authorization": f"Bearer {access_token}"}
            )
        
        def get_full_tools_list(client):
            """
            ページネーションサポートで利用可能な全ツールを一覧表示。
            
            Gatewayはページネーションされたレスポンスでツールを返す可能性があるため、
            完全なリストを取得するためにページネーションを処理する必要があります。
            
            Args:
                client: MCPクライアントインスタンス
                
            Returns:
                list: 利用可能なツールの完全なリスト
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

        # 認証されたトランスポートを使用してMCPクライアントを作成
        mcp_client = MCPClient(create_streamable_http_transport)

        result = None
        try:
            with mcp_client:
                # ステップ3: 認証された接続で利用可能なツールを一覧表示
                logger.info("Step 3: Listing tools via authenticated MCP client...")
                tools = get_full_tools_list(mcp_client)
                tool_names = [tool.tool_name for tool in tools]
                logger.info(f"Available tools: {tool_names}")
                
                if not tools:
                    raise RuntimeError("No tools available from Gateway")
                
                # ステップ4: 認証されたツールでエージェントを作成
                logger.info("Step 4: Creating Strands agent with authenticated tools...")
                agent = Agent(
                    tools=tools,
                    system_prompt="""You are an AWS cost estimation assistant.
                    You help automated systems and services estimate costs for AWS architectures.
                    """
                )
                
                # ステップ5: エージェントを使用してコストを見積もり
                logger.info("Step 5: Running cost estimation with authenticated agent...")
                prompt = (
                    f"Please use the aws_cost_estimation tool to estimate costs for this architecture: "
                    f"{architecture_description}"
                )
            
                result = agent(prompt)
                logger.info("✅ Cost estimation completed successfully")
                
        except Exception as e:
            logger.error(f"Error during cost estimation: {e}")
            return None  # 失敗を示すためにNoneを返す
        
        return result
