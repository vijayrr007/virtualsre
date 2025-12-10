"""Simple way to use MCP tools programmatically.

This directly imports and uses the tools without the transport layer.
Perfect for scripts and automation.
"""

import sys
import os

# Import the tools directly from mcp_server
# Note: We import the underlying functions, not the decorated versions
from kubernetes import config as k8s_config
from kubernetes.client import CoreV1Api, AppsV1Api, CustomObjectsApi


def list_namespaces():
    """List all namespaces."""
    k8s_config.load_kube_config()
    core_v1 = CoreV1Api()
    namespaces = core_v1.list_namespace(watch=False)
    return [ns.to_dict() for ns in namespaces.items]


def list_pods_in_namespace(namespace):
    """List pods in namespace."""
    k8s_config.load_kube_config()
    core_v1 = CoreV1Api()
    pods = core_v1.list_namespaced_pod(namespace=namespace, watch=False)
    return [pod.to_dict() for pod in pods.items]


def list_nodes():
    """List all nodes."""
    k8s_config.load_kube_config()
    core_v1 = CoreV1Api()
    nodes = core_v1.list_node(watch=False)
    return [node.to_dict() for node in nodes.items]


def get_natural_language_response(data, query):
    """Get natural language response using LLM."""
    # Check for API keys
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if openai_key:
        return _call_openai(data, query, openai_key)
    elif anthropic_key:
        return _call_anthropic(data, query, anthropic_key)
    else:
        return f"Raw data (set OPENAI_API_KEY or ANTHROPIC_API_KEY for natural language):\n{data}"


def _call_openai(data, query, api_key):
    """Call OpenAI for interpretation."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""User query: {query}

Kubernetes data:
{str(data)[:2000]}  

Provide a clear, conversational response."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful Kubernetes SRE. Provide clear, concise responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling OpenAI: {e}\n\nRaw data: {data}"


def _call_anthropic(data, query, api_key):
    """Call Anthropic for interpretation."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        
        prompt = f"""User query: {query}

Kubernetes data:
{str(data)[:2000]}

Provide a clear, conversational response."""
        
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            system="You are a helpful Kubernetes SRE. Provide clear, concise responses.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    except Exception as e:
        return f"Error calling Anthropic: {e}\n\nRaw data: {data}"


def main():
    """Run examples."""
    print("=" * 70)
    print("Simple MCP Tools Usage")
    print("=" * 70)
    print()
    
    # Example 1: List namespaces
    print("1. Listing namespaces...")
    namespaces = list_namespaces()
    response = get_natural_language_response(
        [ns['metadata']['name'] for ns in namespaces],
        "List all namespaces"
    )
    print(response)
    print()
    
    # Example 2: List pods
    print("2. Listing pods in kube-system...")
    pods = list_pods_in_namespace("kube-system")
    pod_info = [(p['metadata']['name'], p['status']['phase']) for p in pods]
    response = get_natural_language_response(
        pod_info,
        "List pods in kube-system"
    )
    print(response)
    print()
    
    # Example 3: List nodes
    print("3. Listing nodes...")
    nodes = list_nodes()
    node_info = [n['metadata']['name'] for n in nodes]
    response = get_natural_language_response(
        node_info,
        "List all nodes"
    )
    print(response)
    print()
    
    print("=" * 70)
    print("✅ Done!")
    print()
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("💡 Tip: Set OPENAI_API_KEY or ANTHROPIC_API_KEY for natural language responses!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

