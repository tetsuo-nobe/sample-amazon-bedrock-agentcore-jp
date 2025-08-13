# Amazon Bedrock AgentCore オンボーディング

[English](README_en.md) / [日本語](README.md)

**実践的でシンプル、そして実行可能なサンプル** で、すべての開発者にAmazon Bedrock AgentCoreを効果的に習得していただきます。このプロジェクトでは、AgentCoreの中核機能の実践的な実装を通じて、段階的な学習パスを提供します。

## 概要

Amazon Bedrock AgentCoreは、AIエージェントを大規模に構築、デプロイ、管理するための包括的なプラットフォームです。このオンボーディングプロジェクトでは、各AgentCore機能を **実際に動作する実装** を通じて実演し、実行、変更、学習することができます。

### 学習内容

- **Code Interpreter**: 動的な計算とデータ処理のための安全なサンドボックス実行環境
- **Runtime**: AWSクラウドインフラストラクチャにおけるスケーラブルなエージェントのデプロイと管理
- **Gateway**: 認証とMCPプロトコルサポートを備えたAPIゲートウェイ統合
- **Identity**: エージェント操作のためのOAuth 2.0認証と安全なトークン管理
- **Observability**: CloudWatch統合による包括的なモニタリング、トレーシング、デバッグ
- **Memory**: コンテキストを認識するエージェントのインタラクションのための短期・長期メモリ機能

### 学習理念

私たちの **Amazon Bedrock AgentCore実装原則** に従い、このプロジェクトのすべての例は以下の特徴を持っています：

- ✅ **実行可能なコードファースト** - ライブAWSサービスに対してテストされた、完全で実行可能な例
- ✅ **実践的な実装** - 包括的なロギングとエラーハンドリングを備えた実世界のユースケース
- ✅ **シンプルで洗練された** - 機能性を維持しながら学習コストを最小限に抑える、明確で説明的なコード
- ✅ **段階的な学習** - 基本から高度な概念まで複雑さを徐々に増す番号付きシーケンス

## ディレクトリ構成

```
sample-amazon-bedrock-agentcore-onboarding/
├── 01_code_interpreter/          # 安全なサンドボックス実行環境
│   ├── README.md                 # 📖 Code Interpreterハンズオンガイド
│   ├── cost_estimator_agent/     # AWSコスト見積もりエージェント実装
│   └── test_code_interpreter.py  # 完全なテストスイートとサンプル
│
├── 02_runtime/                   # エージェントのデプロイと管理
│   ├── README.md                 # 📖 Runtimeデプロイハンズオンガイド
│   ├── prepare_agent.py          # エージェント準備自動化ツール
│   ├── agent_package/            # デプロイ用パッケージ化エージェント
│   └── deployment_configs/       # Runtime設定テンプレート
│
├── 03_gateway/                   # 認証付きAPIゲートウェイ
│   ├── README.md                 # 📖 Gateway統合ハンズオンガイド
│   ├── setup_gateway.py          # Gatewayデプロイ自動化
│   ├── lambda_function/          # Lambda統合コード
│   └── test_gateway.py           # MCPクライアントテストサンプル
│
├── 04_identity/                  # OAuth 2.0認証
│   ├── README.md                 # 📖 Identity統合ハンズオンガイド
│   ├── setup_credential_provider.py  # OAuth2プロバイダーセットアップ
│   ├── agent_with_identity.py    # Identity保護されたエージェント
│   └── test_identity_agent.py    # 認証テストスイート
│
├── 05_observability/             # モニタリングとデバッグ
│   └── README.md                 # 📖 Observabilityセットアップハンズオンガイド
│
├── 06_memory/                    # コンテキスト認識インタラクション
│   ├── README.md                 # 📖 Memory統合ハンズオンガイド
│   ├── test_memory.py            # メモリ拡張エージェント実装
│   └── _implementation.md        # 技術的実装詳細
│
├── pyproject.toml                # プロジェクト依存関係と設定
├── uv.lock                       # 依存関係ロックファイル
└── README.md                     # この概要ドキュメント
```

## ハンズオン学習パス

### 🚀 クイックスタート（推奨順序）

1. **[Code Interpreter](01_code_interpreter/README.md)** - 基本的なエージェント開発はここから
   - 安全なPython実行環境でAWSコスト見積もりツールを構築
   - 即座に実践的な結果を得ながらAgentCoreの基本を学習
   - **所要時間**: ~30分 | **難易度**: 初級

2. **[Runtime](02_runtime/README.md)** - エージェントをAWSクラウドインフラストラクチャにデプロイ
   - コスト見積もりツールをAgentCore Runtimeにパッケージ化してデプロイ
   - スケーラブルなエージェントデプロイパターンを理解
   - **所要時間**: ~45分 | **難易度**: 中級

3. **[Gateway](03_gateway/README.md)** - セキュアなAPIを通じてエージェントを公開
   - Lambda統合でMCP互換APIエンドポイントを作成
   - Cognito OAuth認証を実装
   - **所要時間**: ~60分 | **難易度**: 中級

4. **[Identity](04_identity/README.md)** - エージェントに透過的な認証を追加
   - `@requires_access_token`デコレーターでOAuth 2.0を統合
   - 自動トークン管理でエージェント操作を保護
   - **所要時間**: ~30分 | **難易度**: 中級

5. **[Observability](05_observability/README.md)** - 本番エージェントのモニタリングとデバッグ
   - 包括的なモニタリングのためのCloudWatch統合を有効化
   - トレーシング、メトリクス、デバッグ機能をセットアップ
   - **所要時間**: ~20分 | **難易度**: 初級

6. **[Memory](06_memory/README.md)** - コンテキスト認識型の学習エージェントを構築
   - 短期および長期メモリ機能を実装
   - パーソナライズされた適応型エージェント体験を作成
   - **所要時間**: ~45分 | **難易度**: 上級

### 🎯 フォーカス学習（ユースケース別）

**初めてのエージェント構築**
→ [01_code_interpreter](01_code_interpreter/README.md)から開始

**本番環境へのデプロイ**
→ [02_runtime](02_runtime/README.md) → [03_gateway](03_gateway/README.md) → [05_observability](05_observability/README.md)の順序で

**エンタープライズセキュリティ**
→ [04_identity](04_identity/README.md) → [03_gateway](03_gateway/README.md)に焦点を当てる

**高度なAI機能**
→ [06_memory](06_memory/README.md) → [01_code_interpreter](01_code_interpreter/README.md)を探求

## 前提条件

### システム要件
- **Python 3.11+** と `uv` パッケージマネージャー
- 適切な権限で設定された **AWS CLI**
- Bedrock AgentCore（プレビュー版）へのアクセス権を持つ **AWSアカウント**

### クイックセットアップ
```bash
# リポジトリをクローン
git clone <repository-url>
cd sample-amazon-bedrock-agentcore-onboarding

# 依存関係をインストール
uv sync

# AWS設定を確認
aws sts get-caller-identity
```

## 主な特徴

### 🔧 **実装重視**
- ダミーデータやプレースホルダーレスポンスなし
- すべての例がライブAWSサービスに接続
- 本物の複雑さとエラーハンドリングパターン

### 📚 **段階的学習設計**
- 各ディレクトリが前の概念に基づいて構築
- 明確な前提条件と依存関係
- ステップバイステップの実行手順

### 🛠️ **本番環境対応パターン**
- 包括的なエラーハンドリングとロギング
- リソースのクリーンアップとライフサイクル管理
- セキュリティのベストプラクティスと認証

### 🔍 **デバッグしやすい設計**
- 動作をモニタリングするための広範なロギング
- 明確なエラーメッセージとトラブルシューティングガイダンス
- 部分的な障害復旧のための増分状態管理

## サポート

### ドキュメント
- 各ディレクトリには、ハンズオンの指示を含む詳細な`README.md`が含まれています
- 該当する場合は`_implementation.md`ファイルに実装の詳細
- インラインコードコメントで複雑なロジックを説明

### よくある問題
- **AWS権限**: 上記の必要な権限が認証情報にあることを確認してください
- **サービスの可用性**: AgentCoreはプレビュー版です - リージョンの可用性を確認してください
- **依存関係**: 一貫した依存関係バージョンを確保するため`uv sync`を使用してください

### サポートリソース
- [Amazon Bedrock AgentCore開発者ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- アカウント固有の問題については[AWSサポート](https://aws.amazon.com/support/)
- プロジェクト固有の質問については[GitHub Issues](../../issues)

