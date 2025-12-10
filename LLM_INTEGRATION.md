# LLM Integration Guide

Complete guide for integrating your MCP server with LLMs (Large Language Models).

## Two Ways LLMs Work With Your MCP Server

### 1. LLM Consumes Your MCP Tools (Primary Use Case)

This is what your MCP server is designed for:

```
User: "Show me all pods in production namespace"
  ↓
LLM (Claude/GPT-4): Decides to call list_pods_in_namespace tool
  ↓
MCP Server: Executes list_pods_in_namespace("production")
  ↓
Kubernetes Cluster: Returns pod data
  ↓
MCP Server: Sends formatted data back
  ↓
LLM: Analyzes and presents results to user
```

**Any LLM with MCP support can use your server!**

### 2. Your MCP Tools Call LLMs (Optional Enhancement)

You can also add tools that call LLMs for analysis:

```
User: "Analyze issues in production"
  ↓
LLM: Calls analyze_pod_issues tool
  ↓
MCP Server: 
  1. Queries Kubernetes
  2. Sends data to another LLM for analysis
  3. Returns AI-powered recommendations
  ↓
Original LLM: Presents analysis to user
```

## Compatible LLMs

### ✅ Native MCP Support

#### 1. Claude (Anthropic)
Claude Desktop and API have native MCP support.

**Setup:**
```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "kubernetes": {
      "command": "python",
      "args": ["/Users/vijaymantena/virtualsre/main.py"],
      "env": {
        "KUBECONFIG": "/Users/vijaymantena/.kube/config"
      }
    }
  }
}
```

**Usage:**
```
You: "Show me all pods in kube-system namespace"
Claude: [Calls your list_pods_in_namespace tool]
        "I found 2 pods in kube-system:
         - coredns-xxx: Running
         - local-path-provisioner-xxx: Running"
```

#### 2. Continue.dev
VS Code extension with MCP support.

**Setup:**
```json
// .continue/config.json
{
  "mcpServers": {
    "kubernetes": {
      "command": "python",
      "args": ["virtualsre/main.py"]
    }
  }
}
```

### ✅ Via MCP Integration

#### 3. OpenAI GPT-4
Can integrate through custom tooling or frameworks.

**Using LangChain:**
```python
from langchain.tools import Tool
from mcp_client import create_client

async def create_langchain_tool():
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async def list_pods(namespace: str):
        async with client:
            return await client.list_pods_in_namespace(namespace)
    
    return Tool(
        name="list_kubernetes_pods",
        func=list_pods,
        description="Lists pods in a Kubernetes namespace"
    )
```

#### 4. Custom LLM Applications
Any application can use your MCP client library:

```python
import asyncio
from mcp_client import create_client

async def ask_llm_about_cluster():
    # Get data from MCP server
    client = create_client(transport="stdio", server_script_path="./mcp_server.py")
    
    async with client:
        pods = await client.list_all_pods()
        nodes = await client.list_nodes()
    
    # Send to your LLM of choice
    prompt = f"""
    Analyze this Kubernetes cluster:
    - {len(nodes)} nodes
    - {len(pods)} pods
    
    What potential issues do you see?
    """
    
    # Call OpenAI, Anthropic, local model, etc.
    # ...
```

## Adding LLM-Calling Tools to Your Server

If you want your MCP tools to call LLMs for analysis:

### 1. Install LLM Libraries

```bash
cd /Users/vijaymantena/virtualsre

# Add to pyproject.toml
# openai>=1.0.0
# anthropic>=0.18.0

uv add openai anthropic
```

### 2. Set API Keys

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Or add to .env file
echo "OPENAI_API_KEY=sk-..." >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### 3. Add LLM-Calling Tools

See `mcp_server_with_llm.py` for examples:

```python
@mcp.tool()
def analyze_pod_issues(
    namespace: str,
    use_llm: str = "openai"
) -> Dict[str, Any]:
    """
    Analyze pod issues using LLM.
    
    This tool:
    1. Queries Kubernetes for pod data
    2. Sends data to LLM for analysis
    3. Returns AI-powered recommendations
    """
    # Get pod data
    pods = list_pods_in_namespace(namespace)
    
    # Call LLM for analysis
    from openai import OpenAI
    client = OpenAI()
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a Kubernetes SRE expert."},
            {"role": "user", "content": f"Analyze these pods: {pods}"}
        ]
    )
    
    return {
        "pod_data": pods,
        "analysis": response.choices[0].message.content
    }
```

## Use Cases

### 1. LLM Uses Your Tools (Recommended)

**Best for:**
- Interactive troubleshooting
- Natural language queries
- Workflow automation
- Documentation generation

**Example:**
```
User: "Why is my nginx pod failing?"

LLM Process:
1. Calls list_pods_in_namespace("production")
2. Identifies nginx pod
3. Calls get_pod_logs("nginx-xxx", "production")
4. Calls list_events_in_namespace("production")
5. Analyzes all data
6. Responds: "Your nginx pod is failing because..."
```

### 2. Your Tools Call LLMs (Advanced)

**Best for:**
- Complex analysis
- Pattern recognition
- Recommendations
- Anomaly detection

**Example:**
```python
# Tool that uses LLM for analysis
@mcp.tool()
def get_security_recommendations(namespace: str):
    """
    Get AI-powered security recommendations.
    
    This tool:
    1. Scans namespace for security issues
    2. Uses LLM to analyze configurations
    3. Returns specific recommendations
    """
    # Get all resources
    pods = list_pods_in_namespace(namespace)
    services = list_services_in_namespace(namespace)
    configmaps = list_configmaps_in_namespace(namespace)
    
    # LLM analyzes for security issues
    analysis = call_llm_for_security_analysis(pods, services, configmaps)
    
    return analysis
```

## Multi-LLM Architecture

You can combine multiple LLMs:

```
┌──────────────┐
│ Claude       │ ← User interacts
│ (Orchestrator)│
└──────┬───────┘
       │ Calls MCP tools
       ↓
┌──────────────────┐
│   MCP Server     │
│                  │
│  22 K8s Tools    │ ← Query Kubernetes
│                  │
│  + 3 LLM Tools   │ ← Call other LLMs for analysis
└──────┬───────────┘
       │
       ├─→ OpenAI GPT-4 (for code analysis)
       ├─→ Claude Opus (for complex reasoning)
       └─→ Local Llama (for fast queries)
```

## Example: Full Integration

```python
# In your application
import asyncio
from anthropic import Anthropic
from mcp_client import create_client

async def intelligent_cluster_management():
    """Use LLM + MCP for intelligent cluster management."""
    
    # Initialize MCP client
    mcp_client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    # Initialize LLM
    llm = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    async with mcp_client:
        # User asks question
        user_query = "What's the health status of my cluster?"
        
        # LLM decides what tools to call
        # (In practice, Claude would do this automatically via MCP)
        
        # Get cluster data
        nodes = await mcp_client.list_nodes()
        pods = await mcp_client.list_all_pods()
        
        # LLM analyzes
        response = llm.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system="You are a Kubernetes SRE. Analyze cluster health.",
            messages=[{
                "role": "user",
                "content": f"Nodes: {nodes}\nPods: {pods}\n\n{user_query}"
            }]
        )
        
        print(response.content[0].text)

asyncio.run(intelligent_cluster_management())
```

## Testing LLM Integration

### Test Claude Desktop Integration

1. Configure Claude Desktop (see above)
2. Restart Claude Desktop
3. Ask: "List all pods in kube-system namespace"
4. Claude should call your MCP tool and show results

### Test Custom LLM Integration

```python
# test_llm_integration.py
import asyncio
from mcp_client import create_client
from openai import OpenAI

async def test():
    # Start MCP server
    client = create_client(transport="stdio", server_script_path="./mcp_server.py")
    
    async with client:
        # Get data via MCP
        pods = await client.list_all_pods()
        
        # Analyze with LLM
        llm = OpenAI()
        response = llm.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Summarize these Kubernetes pods: {pods[:2]}"
            }]
        )
        
        print(response.choices[0].message.content)

asyncio.run(test())
```

## Best Practices

### 1. Tool Docstrings

Your tools already have great docstrings! Keep them:
- Clear and descriptive
- Include PURPOSE, WHEN TO USE, PARAMETERS, RETURNS
- Provide examples

### 2. Error Handling

```python
@mcp.tool()
def my_tool(namespace: str):
    """Tool with good error handling."""
    try:
        result = query_kubernetes(namespace)
        
        if not result:
            return [{"error": "No data found", "namespace": namespace}]
        
        return result
    except Exception as e:
        return [{"error": f"Failed: {str(e)}", "namespace": namespace}]
```

### 3. Rate Limiting

If calling external LLM APIs:

```python
import time
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_llm_call(prompt: str):
    """Cache LLM responses."""
    time.sleep(0.1)  # Rate limit
    return call_llm(prompt)
```

### 4. Cost Management

```python
@mcp.tool()
def expensive_analysis(namespace: str, use_llm: bool = False):
    """
    Analyze namespace (optionally with LLM).
    
    Set use_llm=True only when needed to save API costs.
    """
    data = get_namespace_data(namespace)
    
    if use_llm:
        return analyze_with_llm(data)  # Costs $$$
    else:
        return basic_analysis(data)    # Free
```

## Summary

### Your MCP Server Can:

✅ Be called by ANY LLM that supports MCP (Claude, GPT-4 via integration, etc.)
✅ Optionally call OTHER LLMs for advanced analysis
✅ Work with multiple LLMs simultaneously
✅ Integrate with LangChain, LlamaIndex, and other frameworks
✅ Support both local and cloud-based LLMs

### Next Steps:

1. **Use with Claude Desktop** - Easiest way to test
2. **Integrate with your application** - Use the MCP client
3. **Add LLM-calling tools** - For advanced analysis (optional)
4. **Try multiple LLMs** - Compare results

Your MCP server is LLM-ready out of the box! 🚀


