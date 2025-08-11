"""
Amazon Bedrock AgentCore Code Interpreterを使用したAWSコスト見積もりエージェント

このエージェントは以下の方法を示します:
1. AWS Pricing MCP Serverを使用して価格データを取得
2. セキュアな計算のためにAgentCore Code Interpreterを使用
3. AWSアーキテクチャの包括的なコスト見積もりを提供

主要機能:
- AgentCoreサンドボックスでのセキュアなコード実行
- リアルタイムAWS価格データ
- 包括的なログ出力とエラーハンドリング
- 漸進的な複雑さの構築
"""

import logging
import traceback
import boto3
from contextlib import contextmanager
from typing import Generator, AsyncGenerator
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from strands.handlers.callback_handler import null_callback_handler
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from cost_estimator_agent.config import (
    SYSTEM_PROMPT,
    COST_ESTIMATION_PROMPT,
    DEFAULT_MODEL,
    LOG_FORMAT
)

# デバッグと監視のための包括的なログ設定
logging.basicConfig(
    level=logging.ERROR,  # デフォルトでERRORに設定、詳細が必要な場合はDEBUGに変更可能
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)

# 詳細なエージェント動作のためのStrandsデバッグログを有効化
logging.getLogger("strands").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class AWSCostEstimatorAgent:
    """
    AgentCore Code Interpreterを使用したAWSコスト見積もりエージェント
    
    このエージェントは以下を組み合わせます:
    - リアルタイム価格データのためのMCPプライシングツール（自動利用可能）
    - セキュアな計算のためのAgentCore Code Interpreter
    - クリーンな実装のためのStrands Agentsフレームワーク
    """
    
    def __init__(self, region: str = ""):
        """
        コスト見積もりエージェントを初期化
        
        Args:
            region: AgentCore Code Interpreter用のAWSリージョン
        """
        self.region = region
        if not self.region:
            # 指定されていない場合はboto3セッションからデフォルトリージョンを使用
            self.region = boto3.Session().region_name
        self.code_interpreter = None
        
        logger.info(f"Initializing AWS Cost Estimator Agent in region: {region}")
        
    def _setup_code_interpreter(self) -> None:
        """セキュアな計算のためにAgentCore Code Interpreterをセットアップ"""
        try:
            logger.info("Setting up AgentCore Code Interpreter...")
            self.code_interpreter = CodeInterpreter(self.region)
            self.code_interpreter.start()
            logger.info("✅ AgentCore Code Interpreter session started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to setup Code Interpreter: {e}")
            return  # Handle the error instead of re-raising
    
    def _get_aws_credentials(self) -> dict:
        """
        現在のAWS認証情報を取得（セッショントークンがある場合は含む）
        
        Returns:
            セッショントークンを含む現在のAWS認証情報の辞書
        """
        try:
            logger.info("Getting current AWS credentials...")
            
            # 現在の認証情報を取得するためのセッションを作成
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if credentials is None:
                raise Exception("No AWS credentials found")
            
            # 呼び出し元のアイデンティティを取得して認証情報が機能することを確認
            sts_client = boto3.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            logger.info(f"Using AWS identity: {identity.get('Arn', 'Unknown')}")
            
            # アクセスするために凍結された認証情報を取得
            frozen_creds = credentials.get_frozen_credentials()
            
            credential_dict = {
                "AWS_ACCESS_KEY_ID": frozen_creds.access_key,
                "AWS_SECRET_ACCESS_KEY": frozen_creds.secret_key,
                "AWS_REGION": self.region
            }
            
            # 利用可能な場合はセッショントークンを追加（EC2インスタンスロールが提供）
            if frozen_creds.token:
                credential_dict["AWS_SESSION_TOKEN"] = frozen_creds.token
                logger.info("✅ Using AWS credentials with session token (likely from EC2 instance role)")
            else:
                logger.info("✅ Using AWS credentials without session token")
                
            return credential_dict
            
        except Exception as e:
            logger.error(f"❌ Failed to get AWS credentials: {e}")
            return {}  # フォールバックとして空の辞書を返す

    def _setup_aws_pricing_client(self) -> MCPClient:
        """現在のAWS認証情報でAWS Pricing MCP Clientをセットアップ"""
        try:
            logger.info("Setting up AWS Pricing MCP Client...")
            
            # 現在の認証情報を取得（セッショントークンがある場合は含む）
            aws_credentials = self._get_aws_credentials()
            
            # MCPクライアント用の環境変数を準備
            env_vars = {
                "FASTMCP_LOG_LEVEL": "ERROR",
                **aws_credentials  # 全てのAWS認証情報を含める
            }
            
            aws_pricing_client = MCPClient(
                lambda: stdio_client(StdioServerParameters(
                    command="uvx", 
                    args=["awslabs.aws-pricing-mcp-server@latest"],
                    env=env_vars
                ))
            )
            logger.info("✅ AWS Pricing MCP Client setup successfully with AWS credentials")
            return aws_pricing_client
        except Exception as e:
            logger.error(f"❌ Failed to setup AWS Pricing MCP Client: {e}")
            return None  # フォールバックとしてNoneを返す
    
    
    @tool
    def execute_cost_calculation(self, calculation_code: str, description: str = "") -> str:
        """
        AgentCore Code Interpreterを使用してコスト計算を実行
        
        Args:
            calculation_code: コスト計算用のPythonコード
            description: 計算の内容の説明
            
        Returns:
            計算結果を文字列で返す
        """
        if not self.code_interpreter:
            return "❌ Code Interpreter not initialized"
            
        try:
            logger.info(f"🧮 Executing calculation: {description}")
            logger.debug(f"Code to execute:\n{calculation_code}")
            
            # セキュアなAgentCoreサンドボックス内でコードを実行
            response = self.code_interpreter.invoke("executeCode", {
                "language": "python",
                "code": calculation_code
            })
            
            # レスポンスストリームから結果を抽出
            results = []
            for event in response.get("stream", []):
                if "result" in event:
                    result = event["result"]
                    if "content" in result:
                        for content_item in result["content"]:
                            if content_item.get("type") == "text":
                                results.append(content_item["text"])
            
            result_text = "\n".join(results)
            logger.info("✅ Calculation completed successfully")
            logger.debug(f"Calculation result: {result_text}")
            
            return result_text
            
        except Exception as e:
            logger.exception(f"❌ Calculation failed: {e}")

    @contextmanager
    def _estimation_agent(self) -> Generator[Agent, None, None]:
        """
        コスト見積もりコンポーネント用のコンテキストマネージャー
        
        Yields:
            全てのツールが設定され、リソースが適切に管理されたエージェント
            
        Ensures:
            Code InterpreterとMCPクライアントリソースの適切なクリーンアップ
        """        
        try:
            logger.info("🚀 Initializing AWS Cost Estimation Agent...")
            
            # コンポーネントを順番にセットアップ
            self._setup_code_interpreter()
            aws_pricing_client = self._setup_aws_pricing_client()
            
            # 永続的なMCPコンテキストでエージェントを作成
            with aws_pricing_client:
                pricing_tools = aws_pricing_client.list_tools_sync()
                logger.info(f"Found {len(pricing_tools)} AWS pricing tools")
                
                # execute_cost_calculationとMCPプライシングツールの両方でエージェントを作成
                all_tools = [self.execute_cost_calculation] + pricing_tools
                agent = Agent(
                    model=DEFAULT_MODEL,
                    tools=all_tools,
                    system_prompt=SYSTEM_PROMPT
                )
                
                yield agent
                
        except Exception as e:
            logger.exception(f"❌ Component setup failed: {e}")
            raise
        finally:
            # 成功・失敗に関係なくクリーンアップが実行されることを保証
            self.cleanup()

    def estimate_costs(self, architecture_description: str) -> str:
        """
        Estimate costs for a given architecture description
        
        Args:
            architecture_description: Description of the system to estimate
            
        Returns:
            Cost estimation results as concatenated string
        """
        logger.info("📊 Starting cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            with self._estimation_agent() as agent:
                # エージェントを使用してコスト見積もりリクエストを処理
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                result = agent(prompt)
                
                logger.info("✅ Cost estimation completed")

                if result.message and result.message.get("content"):
                    # 全てのContentBlockからテキストを抽出して連結
                    text_parts = []
                    for content_block in result.message["content"]:
                        if isinstance(content_block, dict) and "text" in content_block:
                            text_parts.append(content_block["text"])
                    return "".join(text_parts) if text_parts else "No text content found."
                else:
                    return "No estimation result."

        except Exception as e:
            logger.exception(f"❌ Cost estimation failed: {e}")
            error_details = traceback.format_exc()
            return f"❌ Cost estimation failed: {e}\n\nStacktrace:\n{error_details}"

    async def estimate_costs_stream(self, architecture_description: str) -> AsyncGenerator[dict, None]:
        """
        Estimate costs for a given architecture description with streaming response
        
        Implements proper delta-based streaming following Amazon Bedrock best practices.
        This addresses the common issue where Strands stream_async() may send overlapping
        content chunks instead of proper deltas.
        
        Args:
            architecture_description: Description of the system to estimate
            
        Yields:
            Streaming events with true delta content (only new text, no duplicates)
            
        Example usage:
            async for event in agent.estimate_costs_stream(description):
                if "data" in event:
                    print(event["data"], end="", flush=True)  # Direct printing, no accumulation needed
        """
        logger.info("📊 Starting streaming cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            with self._estimation_agent() as agent:
                # エージェントを使用してストリーミングでコスト見積もりリクエストを処理
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                
                logger.info("🔄 Streaming cost estimation response...")
                
                # 重複を防ぐための適切なデルタ処理を実装
                # これはAmazon Bedrock ContentBlockDeltaEventパターンに従う
                previous_output = ""
                
                agent_stream = agent.stream_async(prompt, callback_handler=null_callback_handler)
                
                async for event in agent_stream:
                    if "data" in event:
                        current_chunk = str(event["data"])
                        
                        # Bedrockのベストプラクティスに従ってデルタ計算を処理
                        if current_chunk.startswith(previous_output):
                            # これは増分更新 - 新しい部分のみを抽出
                            delta_content = current_chunk[len(previous_output):]
                            if delta_content:  # 実際に新しいコンテンツがある場合のみyield
                                previous_output = current_chunk
                                yield {"data": delta_content}
                        else:
                            # これは完全に新しいチャンクまたはリセット - そのままyield
                            previous_output = current_chunk
                            yield {"data": current_chunk}
                    else:
                        # データ以外のイベント（エラー、メタデータなど）をパススルー
                        yield event
                
                logger.info("✅ Streaming cost estimation completed")

        except Exception as e:
            logger.exception(f"❌ Streaming cost estimation failed: {e}")
            # ストリーミング形式でエラーイベントをyield
            yield {
                "error": True,
                "data": f"❌ Streaming cost estimation failed: {e}\n\nStacktrace:\n{traceback.format_exc()}"
            }

    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources...")
        
        if self.code_interpreter:
            try:
                self.code_interpreter.stop()
                logger.info("✅ Code Interpreter session stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping Code Interpreter: {e}")
            finally:
                self.code_interpreter = None
