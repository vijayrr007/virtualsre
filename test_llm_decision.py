#!/usr/bin/env python
"""Test to verify OpenAI is deciding which tools to call."""

import os
from openai import OpenAI

# Same tools as in chat_with_mcp.py
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_namespaces",
            "description": "List all namespaces in the Kubernetes cluster",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_nodes",
            "description": "List all nodes in the cluster",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_pods_in_namespace",
            "description": "List all pods in a specific namespace",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Namespace to query"}
                },
                "required": ["namespace"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_events_in_namespace",
            "description": "List recent events in a namespace",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Namespace to query"}
                },
                "required": ["namespace"]
            }
        }
    },
]

def test_openai_decisions():
    """Test different queries to see which tools OpenAI chooses."""
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set!")
        return
    
    client = OpenAI(api_key=api_key)
    
    test_queries = [
        "What namespaces exist?",
        "Show me pods in kube-system",
        "What's the cluster status?",
        "Are there any errors in default namespace?",
        "List all nodes",
    ]
    
    print("=" * 70)
    print("Testing OpenAI Tool Decision Making")
    print("=" * 70)
    print()
    
    for query in test_queries:
        print(f"Query: '{query}'")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Kubernetes SRE assistant. Use tools to answer questions."},
                {"role": "user", "content": query}
            ],
            tools=TOOLS,
            tool_choice="auto",
            temperature=0
        )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            print(f"  ✅ OpenAI decided to call {len(message.tool_calls)} tool(s):")
            for tc in message.tool_calls:
                import json
                args = json.loads(tc.function.arguments)
                args_str = ', '.join(f'{k}={v}' for k, v in args.items()) if args else ''
                print(f"     • {tc.function.name}({args_str})")
        else:
            print(f"  ❌ No tool calls - OpenAI responded directly:")
            print(f"     '{message.content}'")
        
        print()

if __name__ == "__main__":
    test_openai_decisions()

