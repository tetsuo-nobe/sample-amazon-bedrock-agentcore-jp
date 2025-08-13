"""
AgentCore Memoryを持つAWSコスト見積もりエージェント

この実装は、AWSコスト見積もりに短期メモリと長期メモリの
両方の機能を追加することで、AgentCore Memoryの機能を示します。

主要機能:
1. 短期メモリ: 比較のためにセッション内で複数のコスト見積もりを保存
2. 長期メモリ: 時間をかけてユーザーの意思決定パターンと好みを学習
3. 比較機能: 複数の見積もりの並べて比較を可能に
4. 意思決定洞察: 過去のパターンに基づいたパーソナライズされた推奨事項を提供

AgentWithMemoryクラスはメモリ機能を既存の
コスト見積もりエージェントと統合し、メモリ使用パターンの包括的な例を提供します。
"""

import sys
import os
import logging
import traceback
import argparse
import json
import boto3
from datetime import datetime

# デバッグと監視のためのログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 01_code_interpreterからインポートするために親ディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "01_code_interpreter"))

from strands import Agent, tool  # noqa: E402
from bedrock_agentcore.memory.client import MemoryClient  # noqa: E402
from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent  # noqa: E402

# プロンプトテンプレート
SYSTEM_PROMPT = """あなたはメモリ機能を持つAWSコスト見積もりエージェントです。

ユーザーを以下で支援できます:
1. estimate: AWSアーキテクチャのコストを計算
2. compare: 複数のコスト見積もりを並べて比較
3. propose: ユーザーの好みと履歴に基づいて最適なアーキテクチャを推奨

常に詳細な説明を提供し、推奨事項を作成する際には
ユーザーの過去の好みを考慮してください。"""

COMPARISON_PROMPT_TEMPLATE = """以下のAWSコスト見積もりを比較し、洞察を提供してください:

ユーザーリクエスト: {request}

見積もり:
{estimates}

以下を提供してください:
1. 各見積もりの概要
2. アーキテクチャ間の主要な違い
3. コスト比較の洞察
4. 比較に基づいた推奨事項
"""

PROPOSAL_PROMPT_TEMPLATE = """以下に基づいてAWSアーキテクチャ提案を生成してください:

ユーザー要件: {requirements}

過去の好みとパターン:
{historical_data}

以下を提供してください:
1. 推奨アーキテクチャの概要
2. 主要コンポーネントとサービス
3. 予想コスト（概算）
4. スケーラビリティの考慮事項
5. セキュリティのベストプラクティス
6. コスト最適化の推奨事項

利用可能な過去の好みに基づいて提案をパーソナライズしてください。
"""


class AgentWithMemory:
    """
    AgentCore Memory機能で強化されたAWSコスト見積もりエージェント
    
    このクラスはコスト見積もりと比較機能を通じて、
    短期メモリと長期メモリの実用的な区別を示します:
    
    - 短期メモリ: 即座比較のためにセッション内で見積もりを保存
    - 長期メモリ: 時間をかけてユーザーの好みと意思決定パターンを学習
    """
    
    def __init__(self, actor_id: str, region: str = "", force_recreate: bool = False):
        """
        メモリ機能でエージェントを初期化
        
        Args:
            actor_id: ユーザー/アクターの一意識別子（メモリ名前空間に使用）
            region: AgentCoreサービス用のAWSリージョン
            force_recreate: Trueの場合、既存のメモリを削除して新しいものを作成
        """
        self.actor_id = actor_id
        self.region = region
        if not self.region:
            # 指定されていない場合はboto3セッションからデフォルトリージョンを使用
            self.region = boto3.Session().region_name
        self.force_recreate = force_recreate
        self.memory_id = None
        self.memory = None
        self.memory_client = None
        self.agent = None
        self.bedrock_runtime = None
        self.session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.info(f"Initializing AgentWithMemory for actor: {actor_id}")
        if force_recreate:
            logger.info("🔄 Force recreate mode enabled - will delete existing memory")
        
        # ユーザー好み戦略でAgentCore Memoryを初期化
        try:
            logger.info("Initializing AgentCore Memory...")
            self.memory_client = MemoryClient(region_name=self.region)
            
            # メモリが既に存在するかチェック
            memory_name = "cost_estimator_memory"
            existing_memories = self.memory_client.list_memories()
            existing_memory = None
            for memory in existing_memories:
                if memory.get('memoryId').startswith(memory_name):
                    existing_memory = memory
                    break

            if existing_memory:
                if not force_recreate:
                    # 既存のメモリを再使用（デフォルト動作）
                    self.memory_id = existing_memory.get('id')
                    self.memory = existing_memory
                    logger.info(f"🔄 Reusing existing memory: {memory_name} (ID: {self.memory_id})")
                    logger.info("✅ Memory reuse successful - skipping creation time!")
                else:            
                    # force_recreateがTrueの場合は既存のメモリを削除
                    memory_id_to_delete = existing_memory.get('id')
                    logger.info(f"🗑️ Force deleting existing memory: {memory_name} (ID: {memory_id_to_delete})")
                    self.memory_client.delete_memory_and_wait(memory_id_to_delete, max_wait=300)
                    logger.info("✅ Existing memory deleted successfully")
                    existing_memory = None

            if existing_memory is None:
                # 新しいメモリを作成
                logger.info("Creating new AgentCore Memory...")
                self.memory = self.memory_client.create_memory_and_wait(
                    name=memory_name,
                    strategies=[{
                        "userPreferenceMemoryStrategy": {
                            "name": "UserPreferenceExtractor",
                            "description": "Extracts user preferences for AWS architecture decisions",
                            "namespaces": [f"/preferences/{self.actor_id}"]
                        }
                    }],
                    event_expiry_days=7,  # 許可される最小値
                )
                self.memory_id = self.memory.get('memoryId')
                logger.info(f"✅ AgentCore Memory created successfully with ID: {self.memory_id}")

            # AI機能用のBedrock Runtimeクライアントを初期化
            self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=self.region)
            logger.info("✅ Bedrock Runtime client initialized")
            
            # コスト見積もりツールとコールバックハンドラーでエージェントを作成
            self.agent = Agent(
                tools=[self.estimate, self.compare, self.propose],
                system_prompt=SYSTEM_PROMPT
            )
            
        except Exception as e:
            logger.exception(f"❌ Failed to initialize AgentWithMemory: {e}")

    def __enter__(self):
        """コンテキストマネージャーエントリ"""
        return self.agent

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了 - デバッグのためデフォルトでメモリを保持"""
        # デバッグを高速化するためデフォルトでメモリを保持
        # 必要に応じて--forceを使用してメモリを再作成
        try:
            if self.memory_client and self.memory_id:
                logger.info("🧹 Memory preserved for reuse (use --force to recreate)")
                logger.info("✅ Context manager exit completed")
        except Exception as e:
            logger.warning(f"⚠️ Error in context manager exit: {e}")

    def list_memory_events(self, max_results: int = 10):
        """デバッグ用にメモリイベントを検査するヘルパーメソッド"""
        try:
            if not self.memory_client or not self.memory_id:
                return "❌ Memory not available"
            
            events = self.memory_client.list_events(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                max_results=max_results
            )
            
            logger.info(f"📋 Found {len(events)} events in memory")
            for i, event in enumerate(events):
                logger.info(f"Event {i+1}: {json.dumps(event, indent=2, default=str)}")
            
            return events
        except Exception as e:
            logger.error(f"❌ Failed to list events: {e}")
            return []

    @tool
    def estimate(self, architecture_description: str) -> str:
        """
        AWSアーキテクチャのコストを見積もり
        
        Args:
            architecture_description: 見積もり対象のAWSアーキテクチャの説明
            
        Returns:
            Cost estimation results
        """
        try:
            logger.info(f"🔍 Estimating costs for: {architecture_description}")
            
            # 既存のコスト見積もりエージェントを使用
            cost_estimator = AWSCostEstimatorAgent(region=self.region)
            result = cost_estimator.estimate_costs(architecture_description)
            # メモリにイベントを保存
            logger.info("Store event to short term memory")
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                messages=[
                    (architecture_description, "USER"),
                    (result, "ASSISTANT")
                ]
            )

            # メモリフックがこのインタラクションを自動的に保存
            logger.info("✅ Cost estimation completed")
            return result
            
        except Exception as e:
            logger.exception(f"❌ Cost estimation failed: {e}")
            return f"❌ Cost estimation failed: {e}"

    @tool
    def compare(self, request: str = "Compare my recent estimates") -> str:
        """
        メモリから複数のコスト見積もりを比較
        
        Args:
            request: 比較対象の説明
            
        Returns:
            見積もりの詳細な比較
        """
        logger.info("📊 Retrieving estimates for comparison...")
        
        if not self.memory_client or not self.memory_id:
            return "❌ Memory not available for comparison"
        
        # メモリから最近の見積もりイベントを取得
        events = self.memory_client.list_events(
            memory_id=self.memory_id,
            actor_id=self.actor_id,
            session_id=self.session_id,
            max_results=4
        )
        
        # 見積もりツール呼び出しをフィルターして解析
        estimates = []
        for event in events:
            try:
                # ペイロードデータを抽出
                _input = ""
                _output = ""
                for payload in event.get('payload', []):
                    if 'conversational' in payload:
                        _message = payload['conversational']
                        _role = _message.get('role', 'unknown')
                        _content = _message.get('content')["text"]

                        if _role == 'USER':
                            _input = _content
                        elif _role == 'ASSISTANT':
                            _output = _content
                    
                    if _input and _output:
                        estimates.append(
                            "\n".join([
                                "## Estimate",
                                f"**Input:**:\n{_input}",
                                f"**Output:**:\n{_output}"
                            ])
                        )
                        _input = ""
                        _output = ""

            except Exception as parse_error:
                logger.warning(f"Failed to parse event: {parse_error}")
                continue
        
        if not estimates:
            raise Exception("ℹ️ No previous estimates found for comparison. Please run some estimates first.") 
        
        # Bedrockを使用して比較を生成
        logger.info(f"🔍 Comparing {len(estimates)} estimates... {estimates}")
        comparison_prompt = COMPARISON_PROMPT_TEMPLATE.format(
            request=request,
            estimates="\n\n".join(estimates)
        )
        
        comparison_result = self._generate_with_bedrock(comparison_prompt)
        
        logger.info(f"✅ Comparison completed for {len(estimates)} estimates")
        return comparison_result

    @tool
    def propose(self, requirements: str) -> str:
        """
        ユーザーの好みと履歴に基づいて最適なアーキテクチャを提案
        
        Args:
            requirements: アーキテクチャのユーザー要件
            
        Returns:
            パーソナライズされたアーキテクチャ推奨
        """
        try:
            logger.info("💡 Generating architecture proposal based on user history...")
            
            if not self.memory_client or not self.memory_id:
                return "❌ Memory not available for personalized recommendations"
            
            # 長期メモリからユーザーの好みとパターンを取得
            memories = self.memory_client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=f"/preferences/{self.actor_id}",
                query=f"User preferences and decision patterns for: {requirements}",
                top_k=3
            )
            contents = [memory.get('content', {}).get('text', '') for memory in memories]

            # Bedrockを使用して提案を生成
            logger.info(f"🔍 Generating proposal with requirements: {requirements}\nHistorical data: {contents}")
            proposal_prompt = PROPOSAL_PROMPT_TEMPLATE.format(
                requirements=requirements,
                historical_data="\n".join(contents) if memories else "No historical data available"
            )
            
            proposal = self._generate_with_bedrock(proposal_prompt)
            
            logger.info("✅ Architecture proposal generated")
            return proposal
            
        except Exception as e:
            logger.exception(f"❌ Proposal generation failed: {e}")
            return f"❌ Proposal generation failed: {e}"

    def _generate_with_bedrock(self, prompt: str) -> str:
        """
        Amazon Bedrock Converse APIを使用してコンテンツを生成
        
        Args:
            prompt: Bedrockに送信するプロンプト
            
        Returns:
            Bedrockから生成されたコンテンツ
        """
        try:
            # 高速でコスト効率の良い生成のためにClaude 3 Haikuを使用
            model_id = "anthropic.claude-3-haiku-20240307-v1:0"
            
            # メッセージを準備
            messages = [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ]
            
            # Converse APIを使用してモデルを呼び出し
            response = self.bedrock_runtime.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig={
                    "maxTokens": 4000,
                    "temperature": 0.9
                }
            )
            
            # レスポンステキストを抽出
            output_message = response['output']['message']
            generated_text = output_message['content'][0]['text']
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Bedrock generation failed: {e}")
            # Bedrockが失敗した場合のシンプルなレスポンスへのフォールバック
            return f"⚠️ AI generation failed. Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="AWS Cost Estimator Agent with AgentCore Memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python test_memory.py              # 既存のメモリを再使用（高速デバッグ）
  python test_memory.py --force      # メモリを強制再作成（クリーンスタート）
        """
    )
    parser.add_argument(
        '--force', 
        action='store_true',
        help='Force delete and recreate memory (slower but clean start)'
    )
    
    args = parser.parse_args()
    
    print("🚀 AWS Cost Estimator Agent with AgentCore Memory")
    print("=" * 60)
    
    if args.force:
        print("🔄 Force mode: Will delete and recreate memory")
    else:
        print("⚡ Fast mode: Will reuse existing memory")
    
    try:
        # 適切なクリーンアップを保証するためにコンテキストマネージャーを使用
        with AgentWithMemory(actor_id="user123", force_recreate=args.force) as agent:
            print("\n📝 Running cost estimates for different architectures...")
            
            # 3つの異なるアーキテクチャのコストを見積もり
            architectures = [
                "Single EC2 t3.micro instance with RDS MySQL for a small blog",
                "Load balanced EC2 t3.small instances with RDS MySQL for medium traffic web app"
            ]
            
            print("\n🔍 Generating estimates...")
            for i, architecture in enumerate(architectures, 1):
                print(f"\n--- Estimate #{i} ---")
                result = agent(f"Please estimate architecture: {architecture}")
                print(result)
                result_text = result.message["content"] if result.message else "No estimation result."
                print(f"Architecture: {architecture}")
                print(f"Result: {result_text[:200]}..." if len(result_text) > 200 else result_text)

            print("\n" + "="*60)
            print("📊 Comparing all estimates...")
            comparison = agent("Could you please compare the estimates I just generated?")
            print(comparison)

            print("\n" + "="*60)
            print("💡 Getting personalized recommendation...")
            proposal = agent("Could you please propose best architecture for my preference?")
            print(proposal)            
            
    except Exception as e:
        logger.exception(f"❌ Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
        print(f"Stacktrace:\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
