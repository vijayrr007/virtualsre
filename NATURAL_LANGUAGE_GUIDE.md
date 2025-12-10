# Natural Language Query Guide

Get Claude-like conversational responses when using the MCP client directly.

## The Difference

### Regular MCP Client (Raw Data)
```python
from mcp_client import create_client

client = create_client(transport="stdio", server_script_path="./mcp_server.py")
async with client:
    pods = await client.list_pods_in_namespace("kube-system")
    print(pods)  # Returns raw Kubernetes data
```

**Output:**
```json
[
  {
    "metadata": {
      "name": "coredns-6cc96b5c97-qclzf",
      "namespace": "kube-system",
      ...
    },
    "spec": {...},
    "status": {...}
  }
]
```

### Natural Language MCP Client (Conversational)
```python
from mcp_client_with_llm import create_natural_language_client

client = create_natural_language_client(llm_provider="openai")
async with client:
    response = await client.ask("Show me pods in kube-system")
    print(response)  # Returns natural language response
```

**Output:**
```
You have 2 pods running in the kube-system namespace:

1. coredns-6cc96b5c97-qclzf - Running
   This is your CoreDNS pod handling DNS resolution for the cluster.

2. local-path-provisioner-774c6665dc-h8rtc - Running  
   This provides local storage provisioning for your cluster.

Both pods are healthy and running normally.
```

## Setup

### 1. Install LLM Library

```bash
cd /Users/vijaymantena/virtualsre

# For OpenAI
uv add openai

# For Anthropic Claude
uv add anthropic

# Or both
uv add openai anthropic
```

### 2. Set API Key

**OpenAI:**
```bash
export OPENAI_API_KEY="sk-..."
```

**Anthropic:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Or add to .env file:**
```bash
echo "OPENAI_API_KEY=sk-..." >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

## Usage

### Option 1: Natural Language Queries

```python
import asyncio
from mcp_client_with_llm import create_natural_language_client

async def main():
    client = create_natural_language_client(
        llm_provider="openai",  # or "anthropic"
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # Ask in natural language
        response = await client.ask("Show me all pods in kube-system")
        print(response)
        
        response = await client.ask("What namespaces exist?")
        print(response)
        
        response = await client.ask("List deployments in production")
        print(response)

asyncio.run(main())
```

### Option 2: Convenience Methods

```python
async def main():
    client = create_natural_language_client(llm_provider="openai")
    
    async with client:
        # Get natural language descriptions
        response = await client.list_pods(namespace="kube-system")
        print(response)
        
        response = await client.list_deployments(namespace="default")
        print(response)
        
        response = await client.cluster_status()
        print(response)
```

### Option 3: Interactive Mode

```python
# Run the example file
python example_natural_language.py

# Choose interactive mode when prompted
```

Or create your own:
```python
async def chat():
    client = create_natural_language_client(llm_provider="openai")
    
    async with client:
        while True:
            query = input("You: ")
            if query.lower() == 'quit':
                break
            
            response = await client.ask(query)
            print(f"Assistant: {response}\n")
```

## Examples

### Example 1: Check Pod Status

```python
async with client:
    response = await client.ask("Are all pods healthy in kube-system?")
    print(response)
```

**Response:**
```
Yes, all pods in kube-system are healthy! You have 2 pods:

- coredns-6cc96b5c97-qclzf: Running (1/1 containers ready)
- local-path-provisioner-774c6665dc-h8rtc: Running (1/1 containers ready)

No issues detected. Your cluster's system components are working normally.
```

### Example 2: Cluster Overview

```python
async with client:
    response = await client.cluster_status()
    print(response)
```

**Response:**
```
Your Kubernetes cluster is running well! Here's the overview:

Nodes: 1 node (orbstack) - Ready
Namespaces: 4 total (default, kube-system, kube-public, kube-node-lease)
Pods: 2 pods running across all namespaces

The cluster is healthy with all nodes ready and pods running normally.
```

### Example 3: Troubleshooting

```python
async with client:
    response = await client.ask("Why might a pod be failing in production?")
    print(response)
```

**Response:**
```
Looking at your production namespace, I don't see any currently failing pods. 
However, if you do encounter pod failures, common causes include:

1. Image pull errors - Check if the container image exists and is accessible
2. Resource constraints - Insufficient memory or CPU
3. Configuration issues - Invalid environment variables or missing secrets
4. Health check failures - Application not responding to liveness/readiness probes

Would you like me to check recent events for any warnings?
```

## Cost Considerations

### OpenAI Pricing (GPT-4o-mini)
- ~$0.15 per 1M input tokens
- ~$0.60 per 1M output tokens
- Each query: typically $0.001 - $0.01

### Anthropic Pricing (Claude Haiku)
- ~$0.25 per 1M input tokens
- ~$1.25 per 1M output tokens  
- Each query: typically $0.001 - $0.02

**Tip:** Use `llm_provider="none"` if you don't need natural language and want raw data for free.

## Comparison

| Feature | Claude Desktop | Natural Language Client | Regular MCP Client |
|---------|---------------|------------------------|-------------------|
| Natural Language | ✅ Yes | ✅ Yes | ❌ No (raw JSON) |
| Easy Queries | ✅ Yes | ✅ Yes | ❌ Manual tool calls |
| Cost | Free | ~$0.001-0.02/query | Free |
| Setup | Configure JSON | Set API key | Just use |
| Customizable | ❌ No | ✅ Yes | ✅ Yes |
| Offline | ❌ No | ❌ No | ✅ Yes |

## When to Use Each

### Use Claude Desktop When:
- ✅ You want the easiest experience
- ✅ You're already using Claude
- ✅ You want zero coding
- ✅ Interactive conversation is important

### Use Natural Language Client When:
- ✅ Building custom applications
- ✅ Need programmatic access with easy responses
- ✅ Want to customize LLM behavior
- ✅ Need to integrate with other tools

### Use Regular MCP Client When:
- ✅ Building automated scripts
- ✅ Need raw data for processing
- ✅ Don't want LLM costs
- ✅ Offline operation required

## Advanced: Customize LLM Behavior

You can customize how the LLM interprets data:

```python
class CustomNLClient(NaturalLanguageMCPClient):
    def _call_openai(self, prompt: str, context: str = "") -> str:
        # Custom system prompt
        system_prompt = """You are a strict SRE who focuses on problems.
Always highlight issues, potential risks, and areas for improvement."""
        
        # Add your custom logic
        # ...
        
        return super()._call_openai(prompt, system_prompt)
```

## Troubleshooting

### "No LLM API key set"
```bash
# Set the appropriate API key
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "Module not found: openai/anthropic"
```bash
# Install the required library
uv add openai
# or
uv add anthropic
```

### Slow Responses
- Use GPT-4o-mini or Claude Haiku (faster, cheaper)
- Reduce max_tokens in the code
- Cache frequent queries

### Inaccurate Responses
- The LLM interprets raw Kubernetes data
- For critical decisions, verify with raw data
- Adjust system prompts for your needs

## Summary

The Natural Language MCP Client gives you **Claude Desktop-like** conversational responses in your own applications, with full control over:

- ✅ Which LLM to use (OpenAI, Anthropic, or none)
- ✅ How queries are interpreted
- ✅ Response formatting
- ✅ Cost management

Try it now:
```bash
cd /Users/vijaymantena/virtualsre
python example_natural_language.py
```

