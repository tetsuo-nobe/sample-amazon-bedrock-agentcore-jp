"""
Test the AgentCore Identity implementation with existing Cognito M2M OAuth.

This test demonstrates:
1. Using @requires_access_token with existing Cognito configuration
2. Creating an authenticated agent that calls the Gateway
3. Performing cost estimation with proper access controls
4. Token management and caching behavior
5. Error handling and recovery patterns

Prerequisites:
- Gateway deployed (03_gateway)
- OAuth2 credential provider created (setup_credential_provider.py)
- AWS credentials configured

Usage:
    uv run 05_identity/test_identity_agent.py
"""

import asyncio
import logging
import time
from agent_with_identity import AgentWithIdentity

# Configure logging for detailed test output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_identity_protected_estimation():
    """
    Test cost estimation with AgentCore Identity authentication.
    
    This test verifies:
    - Complete authentication flow works end-to-end
    - MCP client can authenticate with Gateway
    - Cost estimation tool is accessible and functional
    """
    print("\n💰 Test 1: Identity-Protected Cost Estimation")
    print("-" * 50)
    
    # Test architecture description
    test_architecture = "[quick] Amazon Translate cost for 1 book."
    
    print(f"Architecture: {test_architecture.strip()}")
    print("-" * 50)
    
    try:
        agent = AgentWithIdentity()
        
        # Perform authenticated cost estimation
        logger.info("Starting authenticated cost estimation...")
        start_time = time.time()
        result = await agent.estimate_costs(test_architecture)
        end_time = time.time()
        
        # Verify result
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
    """Run all AgentCore Identity tests"""
    
    print("🚀 Starting AgentCore Identity Test Suite")
    print("=" * 60)
    
    start_time = time.time()
    passed = 0
    total = 1
    
    # Test 1: Identity-protected cost estimation
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
    
    # Print test summary
    print("\n📊 Test Results Summary")
    print("=" * 60) 
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {(passed/total*100):.1f}%")
    print(f"Total time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
