"""
AgentCore SDKを使用してLambdaターゲットを持つAgentCore Gatewayを作成

このスクリプトは設定またはCloudFormationからLambda ARNを自動取得し、
OIDC DNS伝播遅延を処理し、堅牢なリソースクリーンアップを提供します。

使用方法:
  uv run python create_gateway.py                    # Lambda ARNを自動検出
  uv run python create_gateway.py --lambda-arn ARN   # Lambda ARNを明示的に指定
  uv run python create_gateway.py --force            # リソースの強制再作成
"""

import json
import logging
import argparse
import boto3
import time
import requests
from pathlib import Path
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CONFIG_FILE = Path('gateway_config.json')


def main():
    """Lambdaターゲットを持つGatewayを作成するメイン関数"""
    parser = argparse.ArgumentParser(description='Create AgentCore Gateway with Lambda target')
    parser.add_argument('--lambda-arn', help='Lambda function ARN (auto-detected if not provided)')
    parser.add_argument('--force', action='store_true', help='Force recreation of resources')
    args = parser.parse_args()

    try:
        logger.info("Starting AgentCore Gateway setup...")
        
        # Lambda ARNを取得
        lambda_arn = args.lambda_arn or load_lambda_arn()
        logger.info(f"Using Lambda ARN: {lambda_arn}")

        # Gatewayクライアントを初期化
        client = GatewayClient(region_name=boto3.Session().region_name)
        
        # 既存の設定を処理
        existing_config = load_config() if CONFIG_FILE.exists() else None
        
        # 既存の設定に基づいて作成が必要なものを判定
        has_cognito = existing_config and 'cognito' in existing_config
        has_gateway = existing_config and 'gateway_id' in existing_config
        has_target = existing_config and 'target_id' in existing_config
        
        # すべて完了しており強制フラグがない場合、サマリーを表示して終了
        if existing_config and has_cognito and has_gateway and has_target and not args.force:
            logger.info("All components already configured (use --force to recreate)")
            print_config_summary(existing_config)
            return
        
        # 実行予定の内容を表示
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
        
        # ステップ1: Cognito OAuth認証の処理
        if has_cognito:
            logger.info("✅ Reusing existing Cognito configuration")
            cognito_config = existing_config['cognito']
            # 後続のコードとの互換性のためにcognito_resultを再構築
            cognito_result = {
                'client_info': cognito_config,
                'authorizer_config': {
                    # ゲートウェイが存在しない場合のゲートウェイ作成に必要
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

        # ステップ2: Gateway作成の処理
        if has_gateway:
            logger.info("✅ Reusing existing Gateway")
            gateway_id = existing_config['gateway_id']
            gateway_url = existing_config['gateway_url']
            # ターゲット作成用のgatewayオブジェクトを作成
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
            
            # 作成直後にgateway設定を保存
            save_config({
                "gateway_id": gateway_id,
                "gateway_url": gateway_url
            })
            logger.info("✅ Gateway configuration saved")
        
        # OIDCエンドポイントの利用可能性を待機
        logger.info("Waiting for OIDC endpoint to become available...")
        oidc_url = get_oidc_discovery_url(cognito_result)
        
        if not wait_for_oidc_endpoint(oidc_url):
            logger.warning("OIDC endpoint may not be ready, but proceeding...")
        
        # ステップ3: Lambdaターゲット作成の処理
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

            # 必要なcredentialProviderConfigurationsでlambdaターゲットを作成
            # 注意: toolkitのcreate_mcp_gateway_targetはカスタムtarget_payload + credentialsを処理しない
            # 参考: https://github.com/aws/bedrock-agentcore-starter-toolkit/pull/57 
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
            
            # toolkitメソッドがこの組み合わせをサポートしないため、boto3クライアントを直接使用
            bedrock_client = client.session.client('bedrock-agentcore-control')
            target_response = bedrock_client.create_gateway_target(**create_request)
            
            target_id = target_response["targetId"]
            logger.info(f"✓ Lambda target created: {target_id}")
            
            # 5分のタイムアウトでターゲットの準備完了を待機
            max_wait = 300  # 5分
            interval = 5    # 5秒
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
            
            # ターゲット設定を即座に保存
            save_config({
                "target_id": target_id
            })
            logger.info("✅ Target configuration saved")
        
        logger.info("✅ Gateway setup complete!")
        logger.info("Next step: Run 'uv run python test_gateway.py' to test the Gateway")
        
    except Exception as e:
        logger.error(f"Gateway setup failed: {e}")
        return  # 再発生せずにエラーを処理


def load_lambda_arn():
    """設定ファイルまたはCloudFormationスタックからLambda ARNを読み込み"""
    # まず設定ファイルを試行
    if CONFIG_FILE.exists():
        try:
            config = load_config()
            if config.get('lambda_arn'):
                return config['lambda_arn']
        except Exception as e:
            logger.debug(f"Config file read failed: {e}")
    
    # CloudFormationにフォールバック
    logger.info("Checking CloudFormation for Lambda ARN...")
    try:
        cf_client = boto3.client('cloudformation')
        stack_name = "AWS-Cost-Estimator-Agent"
        
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        
        for output in outputs:
            if output['OutputKey'] == 'AgentCoreGatewayFunctionArn':
                lambda_arn = output['OutputValue']
                
                # 将来の使用のために設定に保存
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
    """OIDCディスカバリーエンドポイントが利用可能になるまで待機
    
    実際のテストに基づくと、DNS伝播とサービス初期化の遅延により、
    OIDCエンドポイントが利用可能になるまでに5分以上かかる場合があります。
    """
    start_time = time.time()
    attempt = 1
    
    logger.info(f"⏳ Waiting for OIDC endpoint: {oidc_url}")
    logger.info(f"⏳ Timeout: {max_wait}s, Check interval: {interval}s")
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(oidc_url, timeout=10)
            logger.info(f"⏳ Attempt {attempt}: HTTP {response.status_code}")
            
            # HTTPエラーステータスコード（4xx、5xx）に対して例外を発生
            response.raise_for_status()
            
            if response.status_code == 200:
                elapsed = time.time() - start_time
                logger.info(f"✅ OIDC endpoint available after {elapsed:.1f}s")
                # 実際に有効なJSONかどうかを確認
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
    """Cognito設定からOIDCディスカバリーURLを抽出"""
    user_pool_id = cognito_result['client_info']['user_pool_id']
    region = boto3.Session().region_name
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"


def cleanup_resources(client, config):
    """既存のGatewayリソースをクリーンアップ"""
    try:
        # まずターゲットを削除
        if 'target_id' in config and 'gateway_id' in config:
            client.delete_mcp_gateway_target(config['gateway_id'], config['target_id'])
            logger.info("Deleted Gateway target")
        
        # Gatewayを削除
        if 'gateway_id' in config:
            client.delete_mcp_gateway(config['gateway_id'])
            logger.info("Deleted Gateway")
        
        # Cognitoリソースをクリーンアップ
        cleanup_cognito_resources(config.get('cognito', {}))
        
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
    
    # 古い設定を削除
    try:
        CONFIG_FILE.unlink()
    except OSError:
        pass


def cleanup_cognito_resources(cognito_config):
    """Cognitoリソースを明示的にクリーンアップ"""
    if not cognito_config.get('user_pool_id'):
        return
    
    try:
        cognito_client = boto3.client('cognito-idp')
        user_pool_id = cognito_config['user_pool_id']
        
        # アプリクライアントを削除
        if cognito_config.get('client_id'):
            cognito_client.delete_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=cognito_config['client_id']
            )
        
        # リソースサーバーを削除
        cognito_client.delete_resource_server(
            UserPoolId=user_pool_id,
            Identifier='AWSCostEstimationResourceServer'
        )
        
        # ユーザープールを削除
        cognito_client.delete_user_pool(UserPoolId=user_pool_id)
        logger.info("Cleaned up Cognito resources")
        
    except Exception as e:
        logger.warning(f"Cognito cleanup error: {e}")


def load_config():
    """ファイルから設定を読み込み"""
    with CONFIG_FILE.open('r') as f:
        return json.load(f)


def save_config(updates):
    """新しいデータで設定ファイルを更新"""
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
    """設定のクリーンなサマリーを印刷"""
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
