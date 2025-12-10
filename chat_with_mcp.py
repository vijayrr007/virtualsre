#!/usr/bin/env python
"""Interactive chat using MCP server with OpenAI or AWS Bedrock Claude.

Uses FastMCP's built-in client to properly communicate with the MCP server.
Dynamically fetches ALL tools from the MCP server.
Supports both OpenAI and AWS Bedrock Claude Sonnet 4.5 via .env configuration.
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional
from openai import OpenAI
from fastmcp import FastMCP
from fastmcp.client import Client
from dotenv import load_dotenv
import boto3

# Load environment variables from .env file
load_dotenv()


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


def mcp_tool_to_claude_format(mcp_tool) -> Dict[str, Any]:
    """Convert MCP tool schema to Claude/Bedrock tool calling format."""
    return {
        "toolSpec": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or f"Execute {mcp_tool.name}",
            "inputSchema": {
                "json": mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
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


async def chat_with_mcp_openai(
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


async def chat_with_mcp_bedrock(
    query: str,
    conversation_history: List[Dict],
    bedrock_client,
    mcp_client: Client,
    claude_tools: List[Dict],
    model_id: str,
    system_prompt: str
) -> tuple[str, List[Dict]]:
    """Chat with AWS Bedrock Claude using MCP tools via function calling."""
    try:
        # Bedrock messages (exclude system prompt - it's passed separately)
        messages = [msg for msg in conversation_history if msg["role"] != "system"]
        messages.append({"role": "user", "content": [{"text": query}]})
        
        # Loop to handle multiple rounds of tool calls
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call Bedrock Claude with converse API
            response = bedrock_client.converse(
                modelId=model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                toolConfig={"tools": claude_tools},
                inferenceConfig={
                    "temperature": 0.7,
                    "maxTokens": 4096
                }
            )
            
            stop_reason = response['stopReason']
            output_message = response['output']['message']
            
            # Add assistant message to conversation
            messages.append(output_message)
            
            # Check if Claude wants to call tools
            if stop_reason == 'tool_use':
                # Extract tool calls from message content
                tool_uses = []
                for content in output_message['content']:
                    if 'toolUse' in content:
                        tool_uses.append(content['toolUse'])
                
                if not tool_uses:
                    break
                
                # Show which tools will be called
                tool_names = [tu['name'] for tu in tool_uses]
                print(f"   🔧 Calling {len(tool_names)} tool(s): {', '.join(tool_names)}", flush=True)
                sys.stdout.flush()
                
                # Execute each tool via MCP
                tool_results = []
                for i, tool_use in enumerate(tool_uses, 1):
                    tool_name = tool_use['name']
                    tool_input = tool_use['input']
                    tool_use_id = tool_use['toolUseId']
                    
                    args_str = ', '.join(f'{k}={v}' for k, v in tool_input.items()) if tool_input else ''
                    print(f"   [{i}/{len(tool_names)}] {tool_name}({args_str})", end='', flush=True)
                    sys.stdout.flush()
                    
                    # Call MCP server
                    result = await call_mcp_tool(mcp_client, tool_name, tool_input)
                    print(" ✓", flush=True)
                    sys.stdout.flush()
                    
                    # Smart truncation
                    result_content = smart_truncate_result(result)
                    
                    # Add tool result in Claude format
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"text": result_content}]
                        }
                    })
                
                # Add tool results as user message
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continue loop to check if Claude wants more tool calls
                print("   🤔 Processing results...", flush=True)
                sys.stdout.flush()
                
            else:
                # No more tool calls - we have the final response
                print("   ✅ Complete!", flush=True)
                sys.stdout.flush()
                print()  # Empty line
                sys.stdout.flush()
                
                # Extract text from response
                final_text = ""
                for content in output_message['content']:
                    if 'text' in content:
                        final_text += content['text']
                
                if not final_text:
                    final_text = "I'm not sure how to help."
                
                # Update conversation history (add original query and response)
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


def get_llm_provider() -> tuple[str, Optional[str]]:
    """Detect which LLM provider to use based on environment variables.
    
    Returns:
        tuple[provider_name, api_key]: ("bedrock", key) or ("openai", key) or (None, None)
    """
    bedrock_key = os.getenv("AWS_BEDROCK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if bedrock_key:
        return ("bedrock", bedrock_key)
    elif openai_key:
        return ("openai", openai_key)
    else:
        return (None, None)


async def main():
    """Run interactive chat with MCP server."""
    print("=" * 70)
    print("🤖 Kubernetes Chat (via MCP Server + LLM)")
    print("=" * 70)
    print()
    
    # Detect LLM provider
    provider, api_key = get_llm_provider()
    
    if not provider:
        print("❌ No API key found!")
        print("   Please create a .env file with either:")
        print("   - AWS_BEDROCK_API_KEY=your-key (for Bedrock Claude)")
        print("   - OPENAI_API_KEY=sk-your-key (for OpenAI)")
        print()
        print("   See env.example for template")
        return 1
    
    print(f"✅ Using {provider.upper()} provider")
    
    # Initialize LLM client
    llm_client = None
    model_id = None
    
    if provider == "bedrock":
        try:
            region = os.getenv("AWS_REGION", "us-east-1")
            model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
            
            llm_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=region,
                aws_access_key_id=api_key,
                aws_secret_access_key=api_key  # Using same key for both
            )
            print(f"✅ Bedrock client initialized (region: {region}, model: {model_id})")
        except Exception as e:
            print(f"❌ Bedrock error: {e}")
            return 1
    else:  # OpenAI
        try:
            llm_client = OpenAI(api_key=api_key)
            print("✅ OpenAI client initialized")
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
            
            # Convert MCP tools to appropriate format
            if provider == "bedrock":
                llm_tools = [mcp_tool_to_claude_format(tool) for tool in mcp_tools]
                print(f"✅ Converted {len(llm_tools)} tools to Claude format")
                tool_names = [t["toolSpec"]["name"] for t in llm_tools]
            else:  # OpenAI
                llm_tools = [mcp_tool_to_openai_format(tool) for tool in mcp_tools]
                print(f"✅ Converted {len(llm_tools)} tools to OpenAI format")
                tool_names = [t["function"]["name"] for t in llm_tools]
            
            print(f"📋 Available tools: {', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}")
            
            print()
            print("=" * 70)
            print("Ask about your cluster! I'll call MCP tools to get information.")
            print()
            print("Try: 'What's the cluster status?', 'Show pods in kube-system'")
            print("Commands: 'clear' (reset), 'quit' (exit)")
            print("=" * 70)
            print()
            
            # System prompt
            system_prompt = """You are a Kubernetes SRE assistant with access to MCP tools.

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
            
            # Initialize conversation (OpenAI needs system in messages, Bedrock passes it separately)
            if provider == "openai":
                conversation_history = [{"role": "system", "content": system_prompt}]
            else:
                conversation_history = []
            
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
                    
                    # Get response from appropriate chat function
                    if provider == "bedrock":
                        response, conversation_history = await chat_with_mcp_bedrock(
                            query,
                            conversation_history,
                            llm_client,
                            mcp_client,
                            llm_tools,
                            model_id,
                            system_prompt
                        )
                    else:  # OpenAI
                        response, conversation_history = await chat_with_mcp_openai(
                            query,
                            conversation_history,
                            llm_client,
                            mcp_client,
                            llm_tools
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
