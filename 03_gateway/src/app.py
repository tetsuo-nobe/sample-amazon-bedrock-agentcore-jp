"""
aws_cost_estimationツールを提供するAgentCore Gateway用のシンプルLambda関数

このLambda関数は02_runtimeにデプロイされたAgentCore Runtimeを呼び出し、
コスト見積もりエージェントを使用してAWSコストを見積もります。
"""

import json
import logging
import os
import boto3
import uuid

# ログ設定
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


def lambda_handler(event, context):
    """
    Gatewayからのaws_cost_estimationツール呼び出しを処理
    
    Args:
        event: コスト見積もり対象のアーキテクチャ説明を含む
        context: Gatewayメタデータを持つLambdaコンテキスト。`client_context`には以下が含まれる必要があります
        ClientContext(custom={
            'bedrockAgentCoreGatewayId': 'Y02ERAYBHB'
            'bedrockAgentCoreTargetId': 'RQHDN3J002'
            'bedrockAgentCoreMessageVersion': '1.0'
            'bedrockAgentCoreToolName': 'weather_tool'
            'bedrockAgentCoreSessionId': ''
        },env=None,client=None]
        参考 : https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/02-AgentCore-gateway/01-transform-lambda-into-mcp-tools

    Returns:
        AgentCore Runtimeからのコスト見積もり結果
    """
    try:
        # 入力リクエストをログ出力
        logger.info(f"Received event: {json.dumps(event)}")
        logger.info(f"Context: {context.client_context}")
        
        # コンテキストからツール名を抽出
        tool_name = context.client_context.custom.get('bedrockAgentCoreToolName', '')
        
        # Gatewayによって追加されたプレフィックスを削除（形式: targetName___toolName）
        if "___" in tool_name:
            tool_name = tool_name.split("___")[-1]
        
        logger.info(f"Processing tool: {tool_name}")
        
        # aws_cost_estimationツールであることを確認
        if tool_name != 'aws_cost_estimation':
            return {
                'statusCode': 400,
                'body': f"Unknown tool: {tool_name}"
            }
        
        # イベントからアーキテクチャ説明を取得
        architecture_description = event.get('architecture_description', '')
        if not architecture_description:
            return {
                'statusCode': 400,
                'body': "Missing required parameter: architecture_description"
            }

        # 環境変数からAgentCore Runtime ARNを取得
        runtime_arn = os.environ.get('AGENTCORE_RUNTIME_ARN')
        if not runtime_arn:
            raise ValueError("AGENTCORE_RUNTIME_ARN environment variable not set")
        
        # AgentCore Runtimeを呼び出し
        result = invoke_cost_estimator_runtime(runtime_arn, architecture_description)

        return {
            'statusCode': 200,
            'body': result
        }
        
    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }


def invoke_cost_estimator_runtime(runtime_arn, architecture_description):
    """
    AgentCore Runtime内のコスト見積もりエージェントを呼び出し
    
    Args:
        runtime_arn: AgentCore RuntimeのARN
        architecture_description: 見積もり対象のAWSアーキテクチャの説明
        
    Returns:
        文字列としてのコスト見積もり結果
    """
    # AgentCoreクライアントを初期化
    client = boto3.client('bedrock-agentcore')
    
    # コスト見積もり用のペイロードを準備
    payload = {
        "prompt": architecture_description
    }
    
    # このリクエスト用のセッションIDを生成
    session_id = str(uuid.uuid4())
    
    logger.info(f"Invoking AgentCore Runtime with session: {session_id}")
    
    # ランタイムを呼び出し
    # `Value at 'traceId' failed to satisfy constraint: Member must have length less than or equal to 128`エラーを回避するためにtraceIdを明示的に設定
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode('utf-8'),
        traceId=session_id,
    )
    
    # レスポンスを処理
    if "text/event-stream" in response.get("contentType", ""):    
        # ストリーミングレスポンスを処理
        content = []
        for line in response["response"].iter_lines(chunk_size=10):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]
                    content.append(line)

    elif response.get("contentType") == "application/json":
        # 標準JSONレスポンスを処理
        content = []
        for chunk in response.get("response", []):
            content.append(chunk.decode('utf-8'))
    
    else:
        content = response.get("response", [])
    
    result = ''.join(content)
    return result
