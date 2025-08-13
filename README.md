# Amazon Bedrock AgentCore Onboarding

[English](README.md) / [日本語](README_ja.md)

**Practical, simple, and runnable examples** to onboard every developer to Amazon Bedrock AgentCore effectively. This project provides a progressive learning path through hands-on implementations of core AgentCore capabilities.

## Overview

Amazon Bedrock AgentCore is a comprehensive platform for building, deploying, and managing AI agents at scale. This onboarding project demonstrates each AgentCore capability through **real, working implementations** that you can run, modify, and learn from.

### What You'll Learn

- **Code Interpreter**: Secure sandboxed execution for dynamic calculations and data processing
- **Runtime**: Scalable agent deployment and management in AWS cloud infrastructure  
- **Gateway**: API gateway integration with authentication and MCP protocol support
- **Identity**: OAuth 2.0 authentication and secure token management for agent operations
- **Observability**: Comprehensive monitoring, tracing, and debugging with CloudWatch integration
- **Memory**: Short-term and long-term memory capabilities for context-aware agent interactions

### Learning Philosophy

Following our **Amazon Bedrock AgentCore Implementation Principle**, every example in this project is:

- ✅ **Runnable Code First** - Complete, executable examples tested against live AWS services
- ✅ **Practical Implementation** - Real-world use cases with comprehensive logging and error handling
- ✅ **Simple and Sophisticated** - Clear, descriptive code that minimizes learning cost while maintaining functionality
- ✅ **Progressive Learning** - Numbered sequences that build complexity gradually from basic to advanced concepts

## Directory Structure

```
sample-amazon-bedrock-agentcore-onboarding/
├── 01_code_interpreter/          # Secure sandboxed execution
│   ├── README.md                 # 📖 Code Interpreter hands-on guide
│   ├── cost_estimator_agent/     # AWS cost estimation agent implementation
│   └── test_code_interpreter.py  # Complete test suite and examples
│
├── 02_runtime/                   # Agent deployment and management
│   ├── README.md                 # 📖 Runtime deployment hands-on guide
│   ├── prepare_agent.py          # Agent preparation automation tool
│   ├── agent_package/            # Packaged agent for deployment
│   └── deployment_configs/       # Runtime configuration templates
│
├── 03_gateway/                   # API gateway with authentication
│   ├── README.md                 # 📖 Gateway integration hands-on guide
│   ├── setup_gateway.py          # Gateway deployment automation
│   ├── lambda_function/          # Lambda integration code
│   └── test_gateway.py           # MCP client testing examples
│
├── 04_identity/                  # OAuth 2.0 authentication
│   ├── README.md                 # 📖 Identity integration hands-on guide
│   ├── setup_credential_provider.py  # OAuth2 provider setup
│   ├── agent_with_identity.py    # Identity-protected agent
│   └── test_identity_agent.py    # Authentication testing suite
│
├── 05_observability/             # Monitoring and debugging
│   └── README.md                 # 📖 Observability setup hands-on guide
│
├── 06_memory/                    # Context-aware interactions
│   ├── README.md                 # 📖 Memory integration hands-on guide
│   ├── test_memory.py            # Memory-enhanced agent implementation
│   └── _implementation.md        # Technical implementation details
│
├── pyproject.toml                # Project dependencies and configuration
├── uv.lock                       # Dependency lock file
└── README.md                     # This overview document
```

## Hands-On Learning Path

### 🚀 Quick Start (Recommended Order)

1. **[Code Interpreter](01_code_interpreter/README.md)** - Start here for foundational agent development
   - Build an AWS cost estimator with secure Python execution
   - Learn AgentCore basics with immediate, practical results
   - **Time**: ~30 minutes | **Difficulty**: Beginner

2. **[Runtime](02_runtime/README.md)** - Deploy your agent to AWS cloud infrastructure
   - Package and deploy the cost estimator to AgentCore Runtime
   - Understand scalable agent deployment patterns
   - **Time**: ~45 minutes | **Difficulty**: Intermediate

3. **[Gateway](03_gateway/README.md)** - Expose your agent through secure APIs
   - Create MCP-compatible API endpoints with Lambda integration
   - Implement Cognito OAuth authentication
   - **Time**: ~60 minutes | **Difficulty**: Intermediate

4. **[Identity](04_identity/README.md)** - Add transparent authentication to agents
   - Integrate OAuth 2.0 with the `@requires_access_token` decorator
   - Secure agent operations with automatic token management
   - **Time**: ~30 minutes | **Difficulty**: Intermediate

5. **[Observability](05_observability/README.md)** - Monitor and debug production agents
   - Enable CloudWatch integration for comprehensive monitoring
   - Set up tracing, metrics, and debugging capabilities
   - **Time**: ~20 minutes | **Difficulty**: Beginner

6. **[Memory](06_memory/README.md)** - Build context-aware, learning agents
   - Implement short-term and long-term memory capabilities
   - Create personalized, adaptive agent experiences
   - **Time**: ~45 minutes | **Difficulty**: Advanced

### 🎯 Focused Learning (By Use Case)

**Building Your First Agent**
→ Start with [01_code_interpreter](01_code_interpreter/README.md)

**Production Deployment**
→ Follow [02_runtime](02_runtime/README.md) → [03_gateway](03_gateway/README.md) → [05_observability](05_observability/README.md)

**Enterprise Security**
→ Focus on [04_identity](04_identity/README.md) → [03_gateway](03_gateway/README.md)

**Advanced AI Capabilities**
→ Explore [06_memory](06_memory/README.md) → [01_code_interpreter](01_code_interpreter/README.md)

## Prerequisites

### System Requirements
- **Python 3.11+** with `uv` package manager
- **AWS CLI** configured with appropriate permissions
- **AWS Account** with access to Bedrock AgentCore (Preview)

### Quick Setup
```bash
# Clone the repository
git clone <repository-url>
cd sample-amazon-bedrock-agentcore-onboarding

# Install dependencies
uv sync

# Verify AWS configuration
aws sts get-caller-identity
```

## Key Features

### 🔧 **Real Implementation Focus**
- No dummy data or placeholder responses
- All examples connect to live AWS services
- Authentic complexity and error handling patterns

### 📚 **Progressive Learning Design**
- Each directory builds on previous concepts
- Clear prerequisites and dependencies
- Step-by-step execution instructions

### 🛠️ **Production-Ready Patterns**
- Comprehensive error handling and logging
- Resource cleanup and lifecycle management
- Security best practices and authentication

### 🔍 **Debugging-Friendly**
- Extensive logging for monitoring behavior
- Clear error messages and troubleshooting guidance
- Incremental state management for partial failure recovery

## Getting Help

### Documentation
- Each directory contains detailed `README.md` with hands-on instructions
- Implementation details in `_implementation.md` files where applicable
- Inline code comments explain complex logic

### Common Issues
- **AWS Permissions**: Ensure your credentials have the required permissions listed above
- **Service Availability**: AgentCore is in Preview - check region availability
- **Dependencies**: Use `uv sync` to ensure consistent dependency versions

### Support Resources

- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AWS Support](https://aws.amazon.com/support/) for account-specific issues
- [GitHub Issues](../../issues) for project-specific questions

## Contributing

We welcome contributions that align with our **Implementation Principle**:

1. **Runnable Code First** - All examples must work with current AWS SDK versions
2. **Practical Implementation** - Include comprehensive comments and real-world use cases
3. **Simple and Sophisticated** - Maintain clarity while preserving functionality
4. **Meaningful Structure** - Use descriptive names and logical organization

See our [Contribution Guideline](CONTRIBUTING.md) for detailed guidelines.


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file for details.
