# VirtualSRE Quick Start Guide

Everything you need to get started with your MCP server.

## What You Have

✅ **MCP Server** - 22 Kubernetes/Istio tools  
✅ **Works with Claude Desktop** - Natural language queries  
✅ **Works with your local Orbstack cluster**  
✅ **Simple programmatic access** - For scripts and automation  

## Quick Start Options

### Option 1: Use with Claude Desktop (Easiest)

**Status:** ✅ Already configured and working!

Just ask Claude:
```
"List all pods in kube-system namespace"
"What namespaces exist in my cluster?"
"Show me all nodes"
```

### Option 2: Programmatic Usage (For Scripts)

Use `simple_usage.py` for automation:

```bash
# Basic usage (shows raw data)
python simple_usage.py

# With natural language (optional)
export OPENAI_API_KEY="sk-..."
python simple_usage.py
```

**Customize it for your needs:**
```python
from simple_usage import list_namespaces, list_pods_in_namespace

# Get data
namespaces = list_namespaces()
pods = list_pods_in_namespace("production")

# Process as needed
for pod in pods:
    print(f"{pod['metadata']['name']}: {pod['status']['phase']}")
```

## Essential Files

### Core Files (Don't Touch)
- `mcp_server.py` - The MCP server with 22 tools
- `mcp_client.py` - MCP client library
- `config.py` - Kubernetes configuration
- `main.py` - Server entry point

### Usage Files
- `simple_usage.py` - **START HERE** for programmatic use
- `example_usage.py` - Original examples (uses MCP protocol)

### Verification
- `verify_local_cluster.py` - Test your setup
- `test_kubernetes_connection.py` - Test K8s connection

### Documentation
- `README.md` - Full documentation
- `QUICKSTART.md` - This file!
- `TOOLS_REFERENCE.md` - All 22 tools documented
- `LOCAL_DEVELOPMENT.md` - Local cluster setup
- `LLM_INTEGRATION.md` - LLM integration guide

## Common Tasks

### Verify Everything Works
```bash
python verify_local_cluster.py
```

### Test Kubernetes Connection
```bash
python test_kubernetes_connection.py
```

### Use in Your Scripts
```python
# Copy simple_usage.py as a starting point
cp simple_usage.py my_script.py
# Edit my_script.py for your needs
```

### Check Available Tools
```bash
python main.py --list-contexts
```

## Need Natural Language?

**With Claude Desktop:** Already works!

**Programmatically:** 
```bash
# Set API key
export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY

# Use simple_usage.py
python simple_usage.py
```

## Troubleshooting

**Problem:** Claude Desktop not connecting  
**Solution:** Already fixed! Just restart Claude Desktop

**Problem:** Need to query programmatically  
**Solution:** Use `simple_usage.py` as template

**Problem:** Want raw Kubernetes data  
**Solution:** Run `simple_usage.py` without API keys

## Next Steps

1. ✅ Claude Desktop works - just use it!
2. ✅ For automation - customize `simple_usage.py`
3. ✅ For advanced usage - read `TOOLS_REFERENCE.md`

That's it! 🚀

