# VirtualSRE - Kubernetes MCP Server

An MCP (Model Context Protocol) server that provides **read-only access** to Kubernetes clusters through an LLM-powered chat interface. Query your clusters using natural language with OpenAI or AWS Bedrock Claude.

## ⚡ Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Set Up API Key

Create a `.env` file:

```bash
# For OpenAI
OPENAI_API_KEY=sk-your-key-here

# OR for AWS Bedrock Claude
AWS_BEDROCK_API_KEY=your-bedrock-key
AWS_REGION=us-east-1
```

### 3. Start Chatting!

```bash
python chat_with_mcp.py
```

Example:
```
💬 You: What's running in my cluster?
🔧 Calling: list_namespaces()
🔧 Calling: list_all_pods_summary()
🤖 Assistant: Your cluster has 5 namespaces and 23 pods running...
```

## ✨ Features

- 🤖 **Natural Language Interface** - Chat with your cluster using OpenAI or Bedrock Claude
- 🔒 **Read-Only** - Safe cluster inspection without modification risks
- 📊 **28 Kubernetes Tools** - Pods, deployments, services, Istio, Gateway API
- 🚀 **Two Transports** - STDIO (subprocess) or HTTP (standalone server)
- 🌐 **Multi-Cluster** - Query multiple clusters from kubeconfig
- 💡 **Smart Tools** - Lightweight summary tools for efficiency

## 📖 Usage

### Interactive Chat (Recommended)

#### Default (STDIO)
```bash
python chat_with_mcp.py
```

#### HTTP Server (for multiple clients)
```bash
# Terminal 1 - Start server
python mcp_server.py --transport http --port 5000

# Terminal 2 - Connect client
python chat_with_mcp.py --mcp-transport http --mcp-url http://localhost:5000/mcp
```

#### Auto-start HTTP server
```bash
python chat_with_mcp.py --mcp-transport http --auto-start-server
```

### Chat Commands
- `quit` or `exit` - Exit the chat
- `clear` - Reset conversation history
- Natural language queries about your cluster

### Programmatic Usage

```python
import asyncio
from fastmcp.client import Client

async def main():
    async with Client("./mcp_server.py") as client:
        # List tools
        tools = await client.list_tools()
        
        # Call a tool
        result = await client.call_tool(
            "list_all_pods_summary",
            arguments={}
        )
        print(result)

asyncio.run(main())
```

## 🛠️ Available Tools (28 Total)

### Quick Reference

| Category | Summary Tools | Detailed Tools |
|----------|--------------|----------------|
| **Pods** | `list_all_pods_summary`<br>`list_pods_in_namespace_summary` | `list_all_pods`<br>`list_pods_in_namespace`<br>`get_pod_logs` |
| **Workloads** | - | `list_deployments_in_namespace`<br>`list_statefulsets_in_namespace`<br>`list_daemonsets_in_namespace`<br>`list_jobs_in_namespace`<br>`list_cronjobs_in_namespace` |
| **Network** | - | `list_services_in_namespace`<br>`list_ingresses_in_namespace` |
| **Config** | - | `list_configmaps_in_namespace`<br>`list_secrets_in_namespace` |
| **Cluster** | - | `list_namespaces`<br>`list_nodes`<br>`list_events_in_namespace`<br>`list_available_contexts` |
| **Istio** | - | `list_istio_virtual_services`<br>`list_istio_destination_rules`<br>`list_istio_gateways`<br>`list_istio_service_entries`<br>`list_istio_peer_authentications`<br>`list_istio_authorization_policies` |
| **Gateway API** | `list_gateways_summary`<br>`list_httproutes_summary` | `list_gateways`<br>`list_httproutes` |

**💡 Tip:** Use summary tools by default - they're faster and handle 100+ pods efficiently!

## 🔧 Configuration

### Local Kubernetes

Works with any local Kubernetes setup:
- Docker Desktop, Minikube, Kind, K3s, Orbstack, etc.

```bash
# Verify your cluster
kubectl config current-context
kubectl get nodes

# Start chatting
python chat_with_mcp.py
```

### AWS EKS

```bash
# Configure AWS CLI
aws configure

# Update kubeconfig
aws eks update-kubeconfig --region us-east-1 --name my-cluster

# Start chatting
python chat_with_mcp.py
```

### Multi-Cluster

Your kubeconfig contexts are automatically available:

```bash
# List available clusters
kubectl config get-contexts

# Query specific cluster
💬 You: Show pods in prod-cluster
```

## 🖥️ Claude Desktop Integration

Add to your Claude config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "virtualsre": {
      "command": "python",
      "args": ["/absolute/path/to/virtualsre/mcp_server.py"]
    }
  }
}
```

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "virtualsre": {
      "command": "python",
      "args": ["C:\\path\\to\\virtualsre\\mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop to load the server.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     chat_with_mcp.py                    │
│              (OpenAI/Bedrock + Conversation)            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ├──STDIO──► mcp_server.py (subprocess)
                       │
                       └───HTTP──► mcp_server.py (network)
                                         │
                                         ▼
                               ┌─────────────────┐
                               │  Kubernetes API  │
                               │   28 Tools      │
                               └─────────────────┘
```

## 📋 Project Structure

```
virtualsre/
├── mcp_server.py        # MCP server with 28 Kubernetes tools
├── chat_with_mcp.py     # Interactive LLM chat interface
├── config.py            # Kubeconfig and AWS authentication
├── pyproject.toml       # Dependencies
├── .env.example         # Environment variable template
└── README.md            # This file
```

## 🔒 Security

- ✅ **Read-Only** - No write operations
- ✅ **RBAC Compliant** - Respects Kubernetes permissions
- ✅ **Credential Safety** - Uses existing kubeconfig/AWS credentials
- ✅ **Secret Protection** - Only returns secret metadata, not values

## 🐛 Troubleshooting

### Connection Issues

```bash
# Test cluster access
kubectl get nodes

# Test AWS credentials (for EKS)
aws sts get-caller-identity

# Verify kubeconfig
kubectl config view
```

### Port Already in Use

```bash
# Use a different port
python chat_with_mcp.py --mcp-transport http --mcp-url http://localhost:5555/mcp --auto-start-server
```

### Permission Errors

Ensure your kubeconfig user has these permissions:
- `pods/list`, `deployments/list`, `services/list`
- `namespaces/list`, `nodes/list`

## 🧪 Testing

```bash
# Test STDIO transport
python chat_with_mcp.py

# Test HTTP server
python mcp_server.py --transport http --port 5555

# Test with curl
curl -X POST http://localhost:5555/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'
```

## 📚 Tool Details

### Summary vs Detailed Tools

**Summary Tools** (Recommended):
- Return only essential fields (name, status, age, restarts)
- Fast and efficient for large clusters (100+ pods)
- Use for general queries

**Detailed Tools** (When Needed):
- Return complete specifications and YAML
- Use when debugging or need full configuration
- Slower for large datasets

### Example Tool Calls

```python
# Summary - Fast
await client.call_tool("list_all_pods_summary", {})

# Detailed - Complete info
await client.call_tool("list_all_pods", {})

# With namespace
await client.call_tool("list_pods_in_namespace_summary", {
    "namespace": "kube-system"
})

# With cluster context
await client.call_tool("list_all_pods_summary", {
    "cluster_context": "prod-cluster"
})

# Get pod logs
await client.call_tool("get_pod_logs", {
    "pod_name": "my-pod",
    "namespace": "default",
    "tail_lines": 100
})
```

## 🚀 Advanced Usage

### HTTP Server Options

```bash
# Default port 5000
python mcp_server.py --transport http

# Custom port and host
python mcp_server.py --transport http --host 127.0.0.1 --port 8080

# For production (bind to all interfaces)
python mcp_server.py --transport http --host 0.0.0.0 --port 5000
```

### Environment Variables

```bash
# In .env file
OPENAI_API_KEY=sk-...                                    # OpenAI key
AWS_BEDROCK_API_KEY=...                                  # Bedrock key
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_REGION=us-east-1
```

## 🛣️ Roadmap

**Completed:**
- [x] STDIO and HTTP transports
- [x] Interactive LLM chat (OpenAI + Bedrock)
- [x] 28 comprehensive Kubernetes tools
- [x] Summary and detailed tool variants
- [x] Pod logs retrieval
- [x] Istio service mesh support
- [x] Gateway API support

**Planned:**
- [ ] Real-time log streaming
- [ ] Metrics and monitoring integration
- [ ] Write operations (with safeguards)
- [ ] Multi-cloud support (GKE, AKS)
- [ ] Web UI

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests
4. Submit a pull request

## 📄 License

MIT License

## 🙏 Acknowledgments

Built with:
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP framework
- [Kubernetes Python Client](https://github.com/kubernetes-client/python)
- [Boto3](https://github.com/boto/boto3) - AWS SDK

---

**Need help?** Open an issue or check the [examples](./chat_with_mcp.py) for more usage patterns.
