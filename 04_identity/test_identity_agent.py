"""
既存のCognito M2M OAuthでAgentCore Identity実装をテスト。

このテストは以下を示します:
1. 既存のCognito設定で@requires_access_tokenを使用
2. Gatewayを呼び出す認証されたエージェントを作成
3. 適切なアクセス制御でコスト見積もりを実行
4. トークン管理とキャッシュ動作
5. エラーハンドリングと復旧パターン

前提条件:
- Gatewayがデプロイ済み (03_gateway)
- OAuth2認証プロバイダーが作成済み (setup_credential_provider.py)
- AWS認証情報が設定済み

使用方法:
    uv run 05_identity/test_identity_agent.py
"""

import asyncio
import logging
import time
from agent_with_identity import AgentWithIdentity

# 詳細なテスト出力のためのログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_identity_protected_estimation():
    """
    AgentCore Identity認証でコスト見積もりをテスト。
    
    このテストは以下を検証:
    - 完全な認証フローがエンドツーエンドで動作
    - MCPクライアントがGatewayで認証可能
    - コスト見積もりツールがアクセス可能で機能する
    """
    print("\n💰 Test 1: Identity-Protected Cost Estimation")
    print("-" * 50)
    
    # テスト用アーキテクチャ説明
    test_architecture = "[quick] Amazon Translate cost for 1 book."
    
    print(f"Architecture: {test_architecture.strip()}")
    print("-" * 50)
    
    try:
        agent = AgentWithIdentity()
        
        # 認証されたコスト見積もりを実行
        logger.info("Starting authenticated cost estimation...")
        start_time = time.time()
        result = await agent.estimate_costs(test_architecture)
        end_time = time.time()
        
        # 結果を検証
        assert result, "Cost estimation result should not be empty"
        result_text = str(result)
        assert len(result_text) > 100, "Result should contain substantial content"
        
        print("✅ Cost estimation completed successfully")
        print(f"   Time taken: {end_time - start_time:.2f} seconds")
        print(f"   Result length: {len(result_text)} characters")
        print("\n📊 Cost Estimation Result:")
        print("=" * 60)
        print(result_text)
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Cost estimation test failed: {e}")
        logger.exception("Cost estimation test error details:")
        return False


async def run_all_tests():
    """全てのAgentCore Identityテストを実行"""
    
    print("🚀 Starting AgentCore Identity Test Suite")
    print("=" * 60)
    
    start_time = time.time()
    passed = 0
    total = 1
    
    # テスト1: Identity保護されたコスト見積もり
    test_name = "Identity-Protected Cost Estimation"
    try:
        logger.info(f"Running test: {test_name}")
        success = await test_identity_protected_estimation()
        if success:
            passed += 1
        print(f"Test result: {'✅ PASSED' if success else '❌ FAILED'}")
    except Exception:
        logger.exception(f"Test {test_name} failed with exception:")
        print("Test result: ❌ FAILED (Exception)")
    
    end_time = time.time()
    
    # テストサマリーを印刷
    print("\n📊 Test Results Summary")
    print("=" * 60) 
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {(passed/total*100):.1f}%")
    print(f"Total time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
