#!/usr/bin/env python
"""Interactive chat using MCP server with OpenAI function calling.

Uses FastMCP's built-in client to properly communicate with the MCP server.
Dynamically fetches ALL tools from the MCP server.
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any
from openai import OpenAI
from fastmcp import FastMCP
from fastmcp.client import Client


def mcp_tool_to_openai_format(mcp_tool) -> Dict[str, Any]:
    """Convert MCP tool schema to OpenAI function calling format."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or f"Execute {mcp_tool.name}",
            "parameters": mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema else {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }


def smart_truncate_result(result: Any, max_chars: int = 200000) -> str:
    """Intelligently truncate large results while preserving useful information.
    
    With summary tools, results should rarely exceed this limit.
    Increased to 200K chars to handle large clusters using summary tools.
    """
    result_json = json.dumps(result, default=str)
    
    # If under limit, return as-is (should be common with summary tools)
    if len(result_json) <= max_chars:
        return result_json
    
    # If it's a list, provide a summary with samples
    if isinstance(result, list):
        total_count = len(result)
        # Show more items since summary data is smaller
        sample_size = min(50, total_count)
        summary = {
            "total_items": total_count,
            "showing": sample_size,
            "note": f"Showing first {sample_size} of {total_count} items. Use namespace-specific queries for more.",
            "sample_items": result[:sample_size]
        }
        return json.dumps(summary, default=str)[:max_chars]
    
    # For other types, just truncate with warning
    truncated = result_json[:max_chars]
    return json.dumps({
        "warning": "Result truncated due to size. Consider using summary tools or namespace-specific queries.",
        "partial_data": truncated
    })


async def call_mcp_tool(client: Client, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call an MCP tool via FastMCP client."""
    try:
        result = await client.call_tool(tool_name, arguments)
        # Extract structured content if available
        if hasattr(result, 'structured_content') and result.structured_content:
            return result.structured_content
        elif hasattr(result, 'content') and result.content:
            # Try to parse text content
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                try:
                    return json.loads(text)
                except:
                    return text
        return str(result)
    except Exception as e:
        return {"error": str(e)}


async def chat_with_mcp(
    query: str,
    conversation_history: List[Dict],
    openai_client: OpenAI,
    mcp_client: Client,
    openai_tools: List[Dict]
) -> tuple[str, List[Dict]]:
    """Chat with OpenAI using MCP tools via function calling."""
    try:
        messages = conversation_history + [{"role": "user", "content": query}]
        
        # Loop to handle multiple rounds of tool calls
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call OpenAI with tools
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.7
            )
            
            assistant_message = response.choices[0].message
            
            # Check if OpenAI wants to call tools
            if assistant_message.tool_calls:
                # Show which tools will be called
                tool_names = [tc.function.name for tc in assistant_message.tool_calls]
                print(f"   🔧 Calling {len(tool_names)} tool(s): {', '.join(tool_names)}", flush=True)
                sys.stdout.flush()
                
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        }
                        for tc in assistant_message.tool_calls
                    ]
                })
                
                # Execute each tool via MCP
                for i, tool_call in enumerate(assistant_message.tool_calls, 1):
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    args_str = ', '.join(f'{k}={v}' for k, v in tool_args.items()) if tool_args else ''
                    print(f"   [{i}/{len(tool_names)}] {tool_name}({args_str})", end='', flush=True)
                    sys.stdout.flush()
                    
                    # Call MCP server
                    result = await call_mcp_tool(mcp_client, tool_name, tool_args)
                    print(" ✓", flush=True)
                    sys.stdout.flush()
                    
                    # Smart truncation to handle large results (200K default, enough for summary tools)
                    result_content = smart_truncate_result(result)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content
                    })
                
                # Continue loop to check if OpenAI wants more tool calls
                print("   🤔 Processing results...", flush=True)
                sys.stdout.flush()
                
            else:
                # No more tool calls - we have the final response
                print("   ✅ Complete!", flush=True)
                sys.stdout.flush()
                print()  # Empty line
                sys.stdout.flush()
                
                final_text = assistant_message.content or "I'm not sure how to help."
                conversation_history.append({"role": "user", "content": query})
                conversation_history.append({"role": "assistant", "content": final_text})
                
                return final_text, conversation_history
        
        # If we hit max iterations, return what we have
        print("   ⚠️  Max iterations reached", flush=True)
        sys.stdout.flush()
        conversation_history.append({"role": "user", "content": query})
        conversation_history.append({"role": "assistant", "content": "I've made several tool calls but need to stop here."})
        return "I've made several tool calls but need to stop here.", conversation_history
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        return f"❌ Error: {e}", conversation_history


async def main():
    """Run interactive chat with MCP server."""
    print("=" * 70)
    print("🤖 Kubernetes Chat (via MCP Server + OpenAI)")
    print("=" * 70)
    print()
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set!")
        print("   export OPENAI_API_KEY='sk-...'")
        return 1
    
    print("✅ OpenAI API key found")
    
    # Initialize OpenAI
    try:
        openai_client = OpenAI(api_key=api_key)
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return 1
    
    # Connect to MCP server using FastMCP client
    print("🚀 Connecting to MCP server...")
    
    try:
        async with Client("./mcp_server.py") as mcp_client:
            print("✅ MCP server connected!")
            
            # Fetch ALL tools from MCP server
            mcp_tools = await mcp_client.list_tools()
            print(f"✅ Found {len(mcp_tools)} MCP tools")
            
            # Convert MCP tools to OpenAI format
            openai_tools = [mcp_tool_to_openai_format(tool) for tool in mcp_tools]
            print(f"✅ Converted {len(openai_tools)} tools to OpenAI format")
            
            # Show available tools
            tool_names = [t["function"]["name"] for t in openai_tools]
            print(f"📋 Available tools: {', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}")
            
            print()
            print("=" * 70)
            print("Ask about your cluster! I'll call MCP tools to get information.")
            print()
            print("Try: 'What's the cluster status?', 'Show pods in kube-system'")
            print("Commands: 'clear' (reset), 'quit' (exit)")
            print("=" * 70)
            print()
            
            # Initialize conversation
            conversation_history = [
                {
                    "role": "system",
                    "content": """You are a Kubernetes SRE assistant with access to MCP tools.

CRITICAL: ALWAYS PREFER SUMMARY TOOLS FOR EFFICIENCY
Summary tools return lightweight data (name, status, age, restarts) and can handle 100+ pods.
Detailed tools return full specs and should ONLY be used when explicitly needed.

TOOL SELECTION RULES:

FOR LISTING PODS (use summary by default):
- "list all pods", "show pods", "what's running": Use list_all_pods_summary()
- "list pods in namespace X": Use list_pods_in_namespace_summary(namespace="X")
- "detailed pods", "full pod info", "pod yaml": Use list_all_pods() or list_pods_in_namespace()

FOR CLUSTER HEALTH:
- Call: list_namespaces, list_nodes, list_all_pods_summary
- Check for Failed/Pending pods and high restart counts

FOR DEBUGGING SPECIFIC PODS:
- Use detailed tools: list_all_pods() or list_pods_in_namespace()
- Or use get_pod_logs() for logs

RESPONSE FORMAT:
- Group pods by namespace when showing cluster-wide results
- Highlight issues: Failed/Pending status, restarts > 5, Unscheduled pods
- Provide counts and statistics
- Be concise

Be helpful and proactive in identifying issues."""
                }
            ]
            
            # Chat loop
            while True:
                try:
                    query = input("🤔 You: ").strip()
                    
                    if query.lower() in ['quit', 'exit', 'q', '']:
                        print("\n👋 Goodbye!")
                        break
                    
                    if query.lower() == 'clear':
                        conversation_history = conversation_history[:1]
                        print("🧹 Memory cleared!\n")
                        continue
                    
                    print("💭 Thinking...", flush=True)
                    sys.stdout.flush()
                    
                    # Get response from chat function with ALL MCP tools
                    response, conversation_history = await chat_with_mcp(
                        query,
                        conversation_history,
                        openai_client,
                        mcp_client,
                        openai_tools
                    )
                    
                    if len(conversation_history) > 21:
                        conversation_history = [conversation_history[0]] + conversation_history[-20:]
                    
                    # Print response with aggressive flushing
                    if response:
                        print(f"🤖 Assistant: {response}", flush=True)
                        sys.stdout.flush()
                        print(flush=True)  # Empty line
                        sys.stdout.flush()
                        print("─" * 70, flush=True)  # Visual separator
                        sys.stdout.flush()
                        print(flush=True)  # Another empty line
                        sys.stdout.flush()
                        # Delay to ensure everything is visible
                        await asyncio.sleep(0.3)
                        sys.stdout.flush()
                    else:
                        print("🤖 Assistant: (No response)", flush=True)
                        sys.stdout.flush()
                        print(flush=True)
                        sys.stdout.flush()
                        await asyncio.sleep(0.3)
                    
                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    break
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
