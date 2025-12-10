"""Example: Adding LLM-calling tools to your MCP server.

This demonstrates how to add tools that can call LLMs (OpenAI, Anthropic, etc.)
to analyze Kubernetes data, provide recommendations, or answer questions.
"""

from typing import Optional, Dict, Any, List
import os


# Add these tools to your mcp_server.py if you want LLM integration

def call_openai(prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """Call OpenAI API."""
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OPENAI_API_KEY not set"}
        
        client = OpenAI(api_key=api_key)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        return {
            "success": True,
            "response": response.choices[0].message.content,
            "model": response.model,
            "tokens": response.usage.total_tokens
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def call_anthropic(prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """Call Anthropic Claude API."""
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY not set"}
        
        client = Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt or "You are a helpful Kubernetes SRE assistant.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return {
            "success": True,
            "response": response.content[0].text,
            "model": response.model,
            "tokens": response.usage.input_tokens + response.usage.output_tokens
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# Example MCP tools that call LLMs:

# @mcp.tool()
def analyze_pod_issues(
    namespace: str,
    cluster_context: Optional[str] = None,
    use_llm: str = "openai"
) -> Dict[str, Any]:
    """
    Analyze pod issues in a namespace using LLM.
    
    PURPOSE:
    This tool retrieves pod information and uses an LLM to analyze issues,
    provide diagnostics, and suggest solutions.
    
    WHEN TO USE:
    - Troubleshooting failing pods
    - Getting AI-powered recommendations
    - Analyzing complex pod states
    - Understanding error patterns
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to analyze
    - cluster_context (optional, str): Cluster context name
    - use_llm (optional, str): LLM to use ("openai" or "anthropic")
    
    RETURNS:
    Dictionary containing:
    - pod_data: Raw pod information
    - analysis: LLM analysis of issues
    - recommendations: Suggested actions
    
    EXAMPLE USAGE:
    - Analyze production: analyze_pod_issues(namespace="production")
    - Use Claude: analyze_pod_issues(namespace="default", use_llm="anthropic")
    """
    from mcp_server import list_pods_in_namespace, list_events_in_namespace
    
    # Get pod data
    pods = list_pods_in_namespace(namespace, cluster_context)
    events = list_events_in_namespace(namespace, cluster_context)
    
    if isinstance(pods, list) and pods and "error" in pods[0]:
        return {"error": pods[0]["error"]}
    
    # Find problematic pods
    issues = []
    for pod in pods:
        if isinstance(pod, dict):
            phase = pod.get('status', {}).get('phase', 'Unknown')
            if phase not in ['Running', 'Succeeded']:
                issues.append({
                    "name": pod.get('metadata', {}).get('name'),
                    "phase": phase,
                    "conditions": pod.get('status', {}).get('conditions', [])
                })
    
    # Prepare prompt for LLM
    if issues:
        prompt = f"""Analyze these Kubernetes pod issues in namespace '{namespace}':

Issues found: {len(issues)} pods not in Running/Succeeded state

Pod Details:
"""
        for issue in issues[:5]:  # Limit to first 5
            prompt += f"\n- {issue['name']}: {issue['phase']}"
            if issue['conditions']:
                for cond in issue['conditions']:
                    if cond.get('status') == 'False':
                        prompt += f"\n  • {cond.get('type')}: {cond.get('reason')} - {cond.get('message', '')[:100]}"
        
        prompt += "\n\nProvide:\n1. Root cause analysis\n2. Specific recommendations to fix\n3. Prevention strategies"
        
        system_prompt = "You are an expert Kubernetes SRE. Analyze pod issues and provide actionable recommendations."
        
        # Call LLM
        if use_llm == "anthropic":
            llm_response = call_anthropic(prompt, system_prompt)
        else:
            llm_response = call_openai(prompt, system_prompt)
        
        return {
            "namespace": namespace,
            "total_pods": len(pods),
            "problematic_pods": len(issues),
            "issues": issues,
            "llm_analysis": llm_response
        }
    else:
        return {
            "namespace": namespace,
            "total_pods": len(pods),
            "problematic_pods": 0,
            "status": "All pods are healthy!",
            "llm_analysis": {"response": "No issues detected. All pods are running successfully."}
        }


# @mcp.tool()
def get_cluster_recommendations(
    cluster_context: Optional[str] = None,
    use_llm: str = "openai"
) -> Dict[str, Any]:
    """
    Get LLM-powered recommendations for cluster optimization.
    
    PURPOSE:
    This tool analyzes your cluster configuration and uses an LLM to provide
    recommendations for improvements, security hardening, and best practices.
    
    WHEN TO USE:
    - Cluster health checks
    - Security audits
    - Performance optimization
    - Best practice validation
    
    PARAMETERS:
    - cluster_context (optional, str): Cluster context name
    - use_llm (optional, str): LLM to use ("openai" or "anthropic")
    
    RETURNS:
    Dictionary with LLM recommendations for cluster improvements
    
    EXAMPLE USAGE:
    - Get recommendations: get_cluster_recommendations()
    - Use Claude: get_cluster_recommendations(use_llm="anthropic")
    """
    from mcp_server import list_nodes, list_namespaces, list_all_pods
    
    # Gather cluster data
    nodes = list_nodes(cluster_context)
    namespaces = list_namespaces(cluster_context)
    pods = list_all_pods(cluster_context)
    
    # Prepare cluster summary
    node_count = len(nodes) if isinstance(nodes, list) else 0
    namespace_count = len(namespaces) if isinstance(namespaces, list) else 0
    pod_count = len(pods) if isinstance(pods, list) else 0
    
    # Analyze resource distribution
    pods_per_namespace = {}
    if isinstance(pods, list):
        for pod in pods:
            if isinstance(pod, dict):
                ns = pod.get('metadata', {}).get('namespace', 'unknown')
                pods_per_namespace[ns] = pods_per_namespace.get(ns, 0) + 1
    
    prompt = f"""Analyze this Kubernetes cluster and provide recommendations:

Cluster Overview:
- Nodes: {node_count}
- Namespaces: {namespace_count}
- Total Pods: {pod_count}

Pods per namespace: {pods_per_namespace}

Provide recommendations for:
1. Resource optimization
2. Security hardening
3. High availability improvements
4. Monitoring and observability
5. Best practice compliance

Focus on actionable, specific recommendations."""
    
    system_prompt = "You are a Kubernetes SRE expert. Provide practical, actionable recommendations for cluster improvements."
    
    # Call LLM
    if use_llm == "anthropic":
        llm_response = call_anthropic(prompt, system_prompt)
    else:
        llm_response = call_openai(prompt, system_prompt)
    
    return {
        "cluster_summary": {
            "nodes": node_count,
            "namespaces": namespace_count,
            "total_pods": pod_count,
            "pods_per_namespace": pods_per_namespace
        },
        "recommendations": llm_response
    }


# @mcp.tool()
def explain_kubernetes_resource(
    resource_type: str,
    resource_name: str,
    namespace: str,
    use_llm: str = "openai"
) -> Dict[str, Any]:
    """
    Get LLM explanation of a Kubernetes resource configuration.
    
    PURPOSE:
    This tool retrieves a Kubernetes resource and uses an LLM to explain
    its configuration, purpose, and potential issues in plain language.
    
    WHEN TO USE:
    - Understanding complex configurations
    - Onboarding new team members
    - Documentation generation
    - Configuration review
    
    PARAMETERS:
    - resource_type (required, str): Type of resource (pod, service, deployment)
    - resource_name (required, str): Name of the resource
    - namespace (required, str): Namespace containing the resource
    - use_llm (optional, str): LLM to use ("openai" or "anthropic")
    
    RETURNS:
    Dictionary with LLM explanation of the resource
    
    EXAMPLE USAGE:
    - Explain pod: explain_kubernetes_resource("pod", "nginx-abc", "default")
    - Explain service: explain_kubernetes_resource("service", "api", "production")
    """
    # This would fetch the specific resource and have the LLM explain it
    # Implementation left as exercise
    pass


if __name__ == "__main__":
    print("""
This file shows examples of how to add LLM-calling tools to your MCP server.

To add these to your server:
1. Install LLM libraries: pip install openai anthropic
2. Set API keys: export OPENAI_API_KEY=xxx or export ANTHROPIC_API_KEY=xxx
3. Add the @mcp.tool() decorator to the functions above
4. Import them in your mcp_server.py

Example usage:
    # The MCP server exposes these tools
    # An LLM can call them to get AI-powered analysis
    result = analyze_pod_issues(namespace="production")
    """)


